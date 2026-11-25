"""Deadline reminders: decide who should be nudged about what, and send each nudge once."""
from __future__ import annotations

import logging
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from .db import Assignment, Enrollment, ReminderLog, Submission, User, now

log = logging.getLogger(__name__)


def due_reminders(db: Session, user: User) -> list[dict]:
    """Reminders that are due now for one student and haven't been sent."""
    t = now()
    course_ids = db.scalars(select(Enrollment.course_id).where(Enrollment.user_id == user.id, Enrollment.role == "student")).all()
    if not course_ids:
        return []
    done = set(db.scalars(select(Submission.assignment_id).where(
        Submission.student_id == user.id, Submission.state.in_(("TURNED_IN", "RETURNED")))))
    sent = {(r.assignment_id, r.kind) for r in db.scalars(select(ReminderLog).where(ReminderLog.user_id == user.id))}
    out = []
    for a in db.scalars(select(Assignment).where(Assignment.course_id.in_(course_ids), Assignment.due_at.is_not(None))):
        if a.id in done:
            continue
        hours_left = (a.due_at - t).total_seconds() / 3600
        if hours_left < 0:
            kind = "overdue" if hours_left > -72 else None  # stop nagging after 3 days
        else:
            # the tightest window we're inside, e.g. 20h left with [48, 24, 2] -> "24h"
            windows = [h for h in sorted(user.remind_hours) if hours_left <= h]
            kind = f"{windows[0]}h" if windows else None
        if kind and (a.id, kind) not in sent:
            out.append({"assignment_id": a.id, "title": a.title, "course": a.course.name, "kind": kind,
                        "due_at": a.due_at.isoformat(), "hours_left": round(hours_left, 1)})
    return sorted(out, key=lambda r: r["hours_left"])


def message(r: dict) -> str:
    if r["kind"] == "overdue":
        return f"Overdue: '{r['title']}' ({r['course']}) was due {abs(r['hours_left']):.0f}h ago. Late work may still earn partial marks."
    return f"Reminder: '{r['title']}' ({r['course']}) is due in {r['hours_left']:.0f}h."


def run_cycle(db: Session, notify=None) -> int:
    """Send all due reminders for all students. Safe to run as often as you like."""
    notify = notify or (lambda user, text: log.info("REMINDER to %s: %s", user.email, text))
    count = 0
    for user in db.scalars(select(User).where(User.role == "student")):
        for r in due_reminders(db, user):
            notify(user, message(r))
            db.add(ReminderLog(user_id=user.id, assignment_id=r["assignment_id"], kind=r["kind"]))
            count += 1
    db.commit()
    return count


def history(db: Session, user: User, days: int = 14) -> list[dict]:
    since = now() - timedelta(days=days)
    rows = db.scalars(select(ReminderLog).where(ReminderLog.user_id == user.id, ReminderLog.sent_at >= since)
                      .order_by(ReminderLog.sent_at.desc()))
    return [{"assignment_id": r.assignment_id, "kind": r.kind, "sent_at": r.sent_at.isoformat()} for r in rows]
