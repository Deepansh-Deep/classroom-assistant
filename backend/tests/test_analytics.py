from datetime import timedelta
from types import SimpleNamespace

from classroom.analytics import score_student
from classroom.db import now


def a(i, days, pts=10):
    return SimpleNamespace(id=f"a{i}", title=f"A{i}", due_at=now() + timedelta(days=days), max_points=pts)


def sub(assignment, hours_vs_due=None, grade=None):
    s = SimpleNamespace(assignment=assignment, grade=grade, state="RETURNED" if hours_vs_due is not None else "ASSIGNED",
                        submitted_at=assignment.due_at + timedelta(hours=hours_vs_due) if hours_vs_due is not None else None)
    s.done = hours_vs_due is not None
    s.late = hours_vs_due is not None and hours_vs_due > 0
    return s


def test_future_work_is_not_counted_as_missing():
    work = [a(1, -5), a(2, 5)]
    r = score_student(work, {"a1": sub(work[0], -10, 9)})
    assert r.factors["completion"] == 100 and r.missing == []


def test_no_past_deadlines_means_no_data():
    assert score_student([a(1, 3)], {}).band == "no_data"


def test_missing_and_late_work_lower_the_score_and_explain_why():
    work = [a(i, -10 + i) for i in range(5)]
    good = score_student(work, {w.id: sub(w, -5, 9) for w in work})
    bad = score_student(work, {w.id: sub(w, 20, 6) for w in work[:2]})
    assert good.score > 85 and good.band == "on_track"
    assert bad.band == "at_risk" and len(bad.missing) == 3 and len(bad.late) == 2
    assert any("not submitted" in r for r in bad.reasons)


def test_consistency_rewards_steady_timing():
    work = [a(i, -20 + i * 3) for i in range(5)]
    steady = score_student(work, {w.id: sub(w, -12) for w in work})
    erratic = score_student(work, {w.id: sub(w, h) for w, h in zip(work, [-70, 30, -60, 40, -5])})
    assert steady.factors["consistency"] > erratic.factors["consistency"]
