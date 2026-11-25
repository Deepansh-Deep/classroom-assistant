"""HTTP API. Run: uvicorn classroom.api:app --reload  (then open http://localhost:8000)"""
from __future__ import annotations

import asyncio
import csv
import io
import logging
import secrets
from contextlib import asynccontextmanager
from datetime import datetime, timedelta

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import __version__, db as dbm, demo_data, reminders, search
from .analytics import score_student
from .config import get_settings
from .db import Assignment, Course, Enrollment, Meta, Submission, User, get_db, now
from .security import current_user, issue_token, require_teacher

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
log = logging.getLogger("classroom")
settings = get_settings()
_oauth_states: dict[str, datetime] = {}


async def _reminder_loop():
    while True:
        await asyncio.sleep(600)
        try:
            with dbm.SessionLocal() as db:
                n = reminders.run_cycle(db)
                if n:
                    log.info("Sent %d reminders", n)
        except Exception:
            log.exception("Reminder cycle failed")


def _ensure_demo(db: Session):
    """Seed on first run, and re-seed weekly so demo deadlines never go stale."""
    if not settings.demo_mode:
        return
    meta = db.get(Meta, "demo_seeded_at")
    if not meta or now() - datetime.fromisoformat(meta.value) > timedelta(days=7):
        demo_data.seed(db)
        log.info("Demo classroom seeded")


@asynccontextmanager
async def lifespan(_: FastAPI):
    dbm.init_engine()
    with dbm.SessionLocal() as db:
        _ensure_demo(db)
    task = asyncio.create_task(_reminder_loop())
    yield
    task.cancel()


app = FastAPI(title="Classroom Assistant", version=__version__, lifespan=lifespan,
              description="Deadlines, explainable progress scores and course Q&A on top of Google Classroom.")
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins.split(","), allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])


# ------------------------------------------------------------------ helpers
def my_courses(db: Session, user: User) -> list[tuple[Course, str]]:
    rows = db.execute(select(Course, Enrollment.role).join(Enrollment).where(Enrollment.user_id == user.id)
                      .order_by(Course.name)).all()
    return [(c, r) for c, r in rows]


def course_for(db: Session, user: User, course_id: str) -> tuple[Course, str]:
    for c, role in my_courses(db, user):
        if c.id == course_id:
            return c, role
    raise HTTPException(404, "Course not found")


def student_score(db: Session, course: Course, student_id: str):
    subs = {s.assignment_id: s for s in db.scalars(select(Submission).join(Assignment).where(
        Assignment.course_id == course.id, Submission.student_id == student_id))}
    return score_student(list(course.assignments), subs)


def user_out(u: User) -> dict:
    return {"id": u.id, "name": u.name, "email": u.email, "role": u.role, "avatar_url": u.avatar_url,
            "is_demo": u.is_demo, "remind_hours": u.remind_hours}


def assignment_out(a: Assignment, sub: Submission | None = None) -> dict:
    t = now()
    status = None
    if sub is not None:
        status = ("late" if sub.late else "done") if sub.done else ("missing" if a.due_at and a.due_at < t else "pending")
    return {"id": a.id, "course_id": a.course_id, "course": a.course.name, "title": a.title, "description": a.description,
            "max_points": a.max_points, "due_at": a.due_at.isoformat() if a.due_at else None,
            "hours_left": round((a.due_at - t).total_seconds() / 3600, 1) if a.due_at else None,
            "status": status, "grade": sub.grade if sub else None}


# ------------------------------------------------------------------ system + auth
@app.get("/api/health")
def health(db: Session = Depends(get_db)):
    return {"status": "ok" if dbm.ping(db) else "degraded", "version": __version__, "database": dbm.ping(db),
            "demo_mode": settings.demo_mode, "google_login": settings.google_enabled, "llm": settings.llm_enabled}


class DemoLogin(BaseModel):
    role: str = Field(pattern="^(teacher|student)$")


@app.post("/api/auth/demo")
def demo_login(body: DemoLogin, db: Session = Depends(get_db)):
    if not settings.demo_mode:
        raise HTTPException(404, "Demo mode is off")
    _ensure_demo(db)
    user = demo_data.demo_user(db, body.role)
    return {"token": issue_token(user), "user": user_out(user)}


@app.get("/api/auth/google")
def google_start():
    if not settings.google_enabled:
        raise HTTPException(503, "Google sign-in isn't configured on this server. Use the demo.")
    from .google_sync import auth_url
    state = secrets.token_urlsafe(24)
    _oauth_states[state] = now()
    return {"url": auth_url(state)}


@app.get("/api/auth/google/callback")
def google_callback(code: str, state: str, db: Session = Depends(get_db)):
    issued = _oauth_states.pop(state, None)
    if not issued or now() - issued > timedelta(minutes=10):  # CSRF protection for the OAuth flow
        raise HTTPException(400, "Login link expired, try again")
    from .google_sync import finish_login, sync_user
    user = finish_login(db, code, state)
    try:
        sync_user(db, user)
    except Exception:
        log.exception("Initial sync failed")
    # Token goes in the URL fragment, which browsers never send to servers or log.
    return RedirectResponse(f"{settings.frontend_url}/auth/#token={issue_token(user)}")


@app.get("/api/me")
def me(user: User = Depends(current_user)):
    return user_out(user)


class ReminderPrefs(BaseModel):
    remind_hours: list[int] = Field(min_length=1, max_length=4)


@app.put("/api/me/reminders")
def set_reminders(body: ReminderPrefs, user: User = Depends(current_user), db: Session = Depends(get_db)):
    hours = sorted({h for h in body.remind_hours if 1 <= h <= 168}, reverse=True)
    if not hours:
        raise HTTPException(422, "Pick reminder times between 1 and 168 hours")
    user.remind_hours = hours
    db.merge(user)
    db.commit()
    return user_out(user)


@app.post("/api/sync")
def sync(user: User = Depends(current_user), db: Session = Depends(get_db)):
    if user.is_demo:
        demo_data.seed(db)
        return {"synced": "demo data refreshed"}
    if not settings.google_enabled:
        raise HTTPException(503, "Google sync isn't configured")
    from .google_sync import sync_user
    try:
        return {"synced": sync_user(db, user)}
    except PermissionError as exc:
        raise HTTPException(401, str(exc))


# ------------------------------------------------------------------ dashboard
@app.get("/api/dashboard")
def dashboard(user: User = Depends(current_user), db: Session = Depends(get_db)):
    courses = my_courses(db, user)
    t = now()
    week = t + timedelta(days=7)
    if user.role == "teacher":
        cards, at_risk = [], []
        for c, _ in courses:
            students = [e.user for e in c.enrollments if e.role == "student"]
            scores = [(s, student_score(db, c, s.id)) for s in students]
            valid = [sc.score for _, sc in scores if sc.score is not None]
            past = [a for a in c.assignments if a.due_at and a.due_at < t]
            subs = db.scalars(select(Submission).join(Assignment).where(Assignment.course_id == c.id)).all()
            done = sum(1 for s in subs if s.done and s.assignment.due_at and s.assignment.due_at < t)
            cards.append({"id": c.id, "name": c.name, "section": c.section, "students": len(students),
                          "avg_score": round(sum(valid) / len(valid), 1) if valid else None,
                          "completion": round(100 * done / (len(past) * len(students)), 1) if past and students else None,
                          "due_this_week": sum(1 for a in c.assignments if a.due_at and t <= a.due_at <= week)})
            at_risk += [{"student": s.name, "student_id": s.id, "course": c.name, "course_id": c.id, "score": sc.score,
                         "reason": sc.reasons[0]} for s, sc in scores if sc.band == "at_risk"]
        upcoming = [assignment_out(a) for c, _ in courses for a in c.assignments if a.due_at and t <= a.due_at <= week]
        return {"role": "teacher", "courses": cards, "at_risk": sorted(at_risk, key=lambda r: r["score"]),
                "upcoming": sorted(upcoming, key=lambda a: a["due_at"])}

    items, scores = [], []
    for c, _ in courses:
        subs = {s.assignment_id: s for s in db.scalars(select(Submission).join(Assignment).where(
            Assignment.course_id == c.id, Submission.student_id == user.id))}
        items += [assignment_out(a, subs.get(a.id)) for a in c.assignments]
        sc = score_student(list(c.assignments), subs)
        scores.append({"course_id": c.id, "course": c.name, **sc.dict()})
    return {"role": "student",
            "due_soon": sorted([i for i in items if i["status"] == "pending" and i["hours_left"] is not None and i["hours_left"] <= 24 * 7],
                               key=lambda i: i["hours_left"]),
            "missing": [i for i in items if i["status"] == "missing"],
            "scores": scores,
            "reminders": reminders.due_reminders(db, user)}


# ------------------------------------------------------------------ courses + assignments
@app.get("/api/courses")
def courses(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return [{"id": c.id, "name": c.name, "section": c.section, "description": c.description, "role": r,
             "assignments": len(c.assignments), "students": sum(1 for e in c.enrollments if e.role == "student"),
             "synced_at": c.synced_at.isoformat() if c.synced_at else None} for c, r in my_courses(db, user)]


@app.get("/api/courses/{course_id}/students")
def course_students(course_id: str, user: User = Depends(require_teacher), db: Session = Depends(get_db)):
    c, role = course_for(db, user, course_id)
    if role != "teacher":
        raise HTTPException(403, "You don't teach this course")
    rows = []
    for e in c.enrollments:
        if e.role == "student":
            sc = student_score(db, c, e.user_id)
            rows.append({"id": e.user_id, "name": e.user.name, "email": e.user.email, **sc.dict()})
    return sorted(rows, key=lambda r: (r["score"] is None, r["score"] or 0))


@app.get("/api/courses/{course_id}/students/{student_id}")
def student_detail(course_id: str, student_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    c, role = course_for(db, user, course_id)
    if role != "teacher" and student_id != user.id:
        raise HTTPException(403, "You can only see your own progress")
    stu = db.get(User, student_id)
    if not stu:
        raise HTTPException(404, "Student not found")
    subs = {s.assignment_id: s for s in db.scalars(select(Submission).join(Assignment).where(
        Assignment.course_id == c.id, Submission.student_id == student_id))}
    return {"student": user_out(stu), "course": c.name, **score_student(list(c.assignments), subs).dict(),
            "assignments": [assignment_out(a, subs.get(a.id)) for a in c.assignments]}


@app.get("/api/assignments")
def assignments(scope: str = Query("upcoming", pattern="^(upcoming|past|all)$"),
                user: User = Depends(current_user), db: Session = Depends(get_db)):
    t = now()
    out = []
    for c, role in my_courses(db, user):
        subs = {}
        if role == "student":
            subs = {s.assignment_id: s for s in db.scalars(select(Submission).join(Assignment).where(
                Assignment.course_id == c.id, Submission.student_id == user.id))}
        for a in c.assignments:
            if scope == "upcoming" and (not a.due_at or a.due_at < t):
                continue
            if scope == "past" and (not a.due_at or a.due_at >= t):
                continue
            out.append(assignment_out(a, subs.get(a.id) if role == "student" else None))
    return sorted(out, key=lambda a: a["due_at"] or "9999", reverse=scope == "past")


# ------------------------------------------------------------------ Q&A, reminders, reports
class AskIn(BaseModel):
    question: str = Field(min_length=3, max_length=400)
    course_id: str | None = None


@app.post("/api/ask")
def ask(body: AskIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    ids = [c.id for c, _ in my_courses(db, user)]
    if body.course_id:
        if body.course_id not in ids:
            raise HTTPException(404, "Course not found")
        ids = [body.course_id]
    return search.answer(db, body.question, ids)


@app.get("/api/reminders")
def my_reminders(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return {"due": reminders.due_reminders(db, user), "sent": reminders.history(db, user), "remind_hours": user.remind_hours}


@app.get("/api/reports/{course_id}.csv")
def report(course_id: str, user: User = Depends(require_teacher), db: Session = Depends(get_db)):
    rows = course_students(course_id, user, db)
    c, _ = course_for(db, user, course_id)
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["Student", "Email", "Score", "Band", "Completion %", "On-time %", "Consistency", "Grades %", "Missing", "Late", "Top action"])
    for r in rows:
        f = r["factors"]
        w.writerow([r["name"], r["email"], r["score"], r["band"], f["completion"], f["timeliness"], f["consistency"],
                    f["grades"], len(r["missing"]), len(r["late"]), r["actions"][0] if r["actions"] else ""])
    name = "".join(ch if ch.isalnum() else "-" for ch in c.name).lower()
    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv",
                             headers={"Content-Disposition": f'attachment; filename="{name}-progress-{now():%Y-%m-%d}.csv"'})


# ------------------------------------------------------------------ frontend
if settings.frontend_dir.exists():
    app.mount("/_next", StaticFiles(directory=settings.frontend_dir / "_next"), name="next")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        if path.startswith("api/"):
            raise HTTPException(404)
        for candidate in (settings.frontend_dir / path, settings.frontend_dir / path / "index.html",
                          settings.frontend_dir / f"{path}.html"):
            if candidate.is_file():
                return FileResponse(candidate)
        return FileResponse(settings.frontend_dir / "index.html")
