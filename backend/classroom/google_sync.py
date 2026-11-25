"""Google Classroom OAuth and sync. Only used when GOOGLE_CLIENT_ID/SECRET are set."""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import get_settings
from .db import Assignment, Course, Enrollment, Post, Submission, User, now
from .security import decrypt, encrypt

log = logging.getLogger(__name__)

SCOPES = [
    "openid", "https://www.googleapis.com/auth/userinfo.email", "https://www.googleapis.com/auth/userinfo.profile",
    "https://www.googleapis.com/auth/classroom.courses.readonly",
    "https://www.googleapis.com/auth/classroom.coursework.me.readonly",
    "https://www.googleapis.com/auth/classroom.coursework.students.readonly",
    "https://www.googleapis.com/auth/classroom.announcements.readonly",
    "https://www.googleapis.com/auth/classroom.courseworkmaterials.readonly",
    "https://www.googleapis.com/auth/classroom.rosters.readonly",
]


def _flow(state: str | None = None):
    from google_auth_oauthlib.flow import Flow
    s = get_settings()
    cfg = {"web": {"client_id": s.google_client_id, "client_secret": s.google_client_secret,
                   "auth_uri": "https://accounts.google.com/o/oauth2/auth", "token_uri": "https://oauth2.googleapis.com/token",
                   "redirect_uris": [s.google_redirect_uri]}}
    return Flow.from_client_config(cfg, scopes=SCOPES, state=state, redirect_uri=s.google_redirect_uri)


def auth_url(state: str) -> str:
    url, _ = _flow(state).authorization_url(access_type="offline", prompt="consent", include_granted_scopes="true")
    return url


def finish_login(db: Session, code: str, state: str) -> User:
    from googleapiclient.discovery import build
    flow = _flow(state)
    flow.fetch_token(code=code)
    creds = flow.credentials
    info = build("oauth2", "v2", credentials=creds, cache_discovery=False).userinfo().get().execute()
    user = db.scalar(select(User).where(User.google_id == info["id"])) or db.scalar(select(User).where(User.email == info["email"]))
    if not user:
        user = User(email=info["email"], name=info.get("name") or info["email"], google_id=info["id"])
        db.add(user)
    user.google_id, user.avatar_url = info["id"], info.get("picture")
    if creds.refresh_token:
        user.refresh_token_enc = encrypt(creds.refresh_token)
    db.commit()
    return user


def _credentials(user: User):
    from google.oauth2.credentials import Credentials
    s = get_settings()
    token = decrypt(user.refresh_token_enc or "")
    if not token:
        raise PermissionError("Google access expired. Sign in with Google again.")
    return Credentials(None, refresh_token=token, token_uri="https://oauth2.googleapis.com/token",
                       client_id=s.google_client_id, client_secret=s.google_client_secret, scopes=SCOPES)


def _pages(method, key, **kw):
    token = None
    while True:
        resp = method(pageToken=token, **kw).execute()
        yield from resp.get(key, [])
        token = resp.get("nextPageToken")
        if not token:
            return


def _ts(v: str | None) -> datetime | None:
    return datetime.fromisoformat(v.replace("Z", "+00:00")) if v else None


def _due(item: dict) -> datetime | None:
    d = item.get("dueDate")
    if not d:
        return None
    t = item.get("dueTime", {})
    return datetime(d["year"], d["month"], d["day"], t.get("hours", 23), t.get("minutes", 59), tzinfo=timezone.utc)


def _upsert(db: Session, model, external_id: str, **fields):
    obj = db.scalar(select(model).where(model.external_id == external_id))
    if not obj:
        obj = model(external_id=external_id)
        db.add(obj)
    for k, v in fields.items():
        setattr(obj, k, v)
    db.flush()
    return obj


def sync_user(db: Session, user: User) -> dict:
    """Pull every active course of this user. Idempotent: safe to run repeatedly."""
    from googleapiclient.discovery import build
    svc = build("classroom", "v1", credentials=_credentials(user), cache_discovery=False)
    counts = {"courses": 0, "assignments": 0, "submissions": 0, "posts": 0}
    for c in _pages(svc.courses().list, "courses", courseStates=["ACTIVE"]):
        course = _upsert(db, Course, c["id"], name=c["name"], section=c.get("section"),
                         description=c.get("descriptionHeading"), synced_at=now())
        counts["courses"] += 1
        teaching = c.get("ownerId") == user.google_id
        role = "teacher" if teaching else "student"
        if role == "teacher":
            user.role = "teacher"
        if not db.scalar(select(Enrollment).where(Enrollment.user_id == user.id, Enrollment.course_id == course.id)):
            db.add(Enrollment(user_id=user.id, course_id=course.id, role=role))

        students = {}
        if teaching:
            for st in _pages(svc.courses().students().list, "students", courseId=c["id"]):
                p = st["profile"]
                u = db.scalar(select(User).where(User.google_id == p["id"]))
                if not u:
                    u = User(google_id=p["id"], email=p.get("emailAddress") or f"{p['id']}@unknown", name=p["name"]["fullName"])
                    db.add(u)
                    db.flush()
                if not db.scalar(select(Enrollment).where(Enrollment.user_id == u.id, Enrollment.course_id == course.id)):
                    db.add(Enrollment(user_id=u.id, course_id=course.id, role="student"))
                students[p["id"]] = u
        else:
            students[user.google_id] = user

        for w in _pages(svc.courses().courseWork().list, "courseWork", courseId=c["id"]):
            a = _upsert(db, Assignment, w["id"], course_id=course.id, title=w["title"], description=w.get("description"),
                        max_points=w.get("maxPoints"), due_at=_due(w), created_at=_ts(w.get("creationTime")) or now())
            counts["assignments"] += 1
            for s in _pages(svc.courses().courseWork().studentSubmissions().list, "studentSubmissions",
                            courseId=c["id"], courseWorkId=w["id"]):
                stu = students.get(s["userId"])
                if not stu:
                    continue
                sub = db.scalar(select(Submission).where(Submission.assignment_id == a.id, Submission.student_id == stu.id))
                if not sub:
                    sub = Submission(assignment_id=a.id, student_id=stu.id)
                    db.add(sub)
                sub.state = s["state"] if s["state"] in ("TURNED_IN", "RETURNED") else "ASSIGNED"
                turned_in = [h["stateHistory"]["stateTimestamp"] for h in s.get("submissionHistory", [])
                             if h.get("stateHistory", {}).get("state") == "TURNED_IN"]
                sub.submitted_at = _ts(turned_in[-1]) if turned_in else None
                sub.grade = s.get("assignedGrade")
                counts["submissions"] += 1

        for an in _pages(svc.courses().announcements().list, "announcements", courseId=c["id"]):
            _upsert(db, Post, an["id"], course_id=course.id, kind="announcement", title=None,
                    text=an.get("text", ""), posted_at=_ts(an.get("creationTime")) or now())
            counts["posts"] += 1
        for m in _pages(svc.courses().courseWorkMaterials().list, "courseWorkMaterial", courseId=c["id"]):
            _upsert(db, Post, m["id"], course_id=course.id, kind="material", title=m.get("title"),
                    text=m.get("description") or m.get("title", ""), posted_at=_ts(m.get("creationTime")) or now())
            counts["posts"] += 1
    db.commit()
    return counts
