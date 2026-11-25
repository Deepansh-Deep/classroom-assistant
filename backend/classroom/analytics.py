"""Explainable performance scores. Rules, not a model: every number can be traced to submissions.

Changes from v1:
- Consistency now measures how steady a student's timing is *relative to each
  deadline* (std-dev of hours early/late). v1 measured gaps between submission
  dates, which mostly reflected the teacher's assignment schedule.
- Only assignments whose deadline has passed count. v1 counted future work as missing.
- Late penalties for missing work no longer double count: timeliness only looks at
  submitted work, completion handles missing work.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from statistics import pstdev
from typing import Optional

from .db import Assignment, Submission, now

WEIGHTS = {"completion": 0.35, "timeliness": 0.25, "consistency": 0.15, "grades": 0.25}


@dataclass
class Score:
    score: Optional[float]
    band: str  # on_track | needs_attention | at_risk | no_data
    factors: dict[str, Optional[float]]
    reasons: list[str] = field(default_factory=list)
    actions: list[str] = field(default_factory=list)
    counted: int = 0
    missing: list[str] = field(default_factory=list)
    late: list[str] = field(default_factory=list)

    def dict(self):
        return asdict(self)


def score_student(assignments: list[Assignment], subs_by_assignment: dict[str, Submission]) -> Score:
    t = now()
    past = [a for a in assignments if a.due_at and a.due_at < t]
    if not past:
        return Score(None, "no_data", {k: None for k in WEIGHTS}, ["No deadlines have passed yet."])

    done = [(a, subs_by_assignment[a.id]) for a in past if a.id in subs_by_assignment and subs_by_assignment[a.id].done]
    missing = [a.title for a in past if not (a.id in subs_by_assignment and subs_by_assignment[a.id].done)]
    late = [a.title for a, s in done if s.late]

    completion = 100 * len(done) / len(past)
    timeliness = 100 * (len(done) - len(late)) / len(done) if done else None
    offsets = [(s.submitted_at - a.due_at).total_seconds() / 3600 for a, s in done if s.submitted_at]
    # 0h spread -> 100. A spread of 48h or more (sometimes days early, sometimes days late) -> 0.
    consistency = max(0.0, 100 - pstdev(offsets) * 100 / 48) if len(offsets) >= 3 else None
    graded = [(s.grade, a.max_points) for a, s in done if s.grade is not None and a.max_points]
    grades = 100 * sum(g for g, _ in graded) / sum(m for _, m in graded) if graded else None

    factors = {"completion": completion, "timeliness": timeliness, "consistency": consistency, "grades": grades}
    known = {k: v for k, v in factors.items() if v is not None}
    total_w = sum(WEIGHTS[k] for k in known)
    score = sum(v * WEIGHTS[k] for k, v in known.items()) / total_w
    band = "on_track" if score >= 75 else "needs_attention" if score >= 55 else "at_risk"

    reasons, actions = [], []
    if missing:
        reasons.append(f"{len(missing)} of {len(past)} past assignments not submitted.")
        actions.append(f"Submit '{missing[0]}' first; missing work costs the most.")
    else:
        reasons.append(f"All {len(past)} past assignments submitted.")
    if timeliness is not None:
        if late:
            reasons.append(f"{len(late)} of {len(done)} submissions were late.")
            actions.append("Aim to submit a day early; most late work here was within 48 hours of the deadline.")
        else:
            reasons.append("Every submission was on time.")
    if consistency is not None and consistency < 50:
        reasons.append("Timing swings a lot: sometimes days early, sometimes days late.")
        actions.append("Block a fixed weekly slot for coursework instead of working in bursts.")
    if grades is not None:
        reasons.append(f"Average grade on returned work: {grades:.0f}%.")
        if grades < 60:
            actions.append("Use office hours for the topics you lost most marks on.")
    if not actions:
        actions.append("Keep the current routine.")

    r = lambda x: None if x is None else round(x, 1)  # noqa: E731
    return Score(round(score, 1), band, {k: r(v) for k, v in factors.items()}, reasons, actions,
                 counted=len(past), missing=missing, late=late)
