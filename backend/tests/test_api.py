from conftest import login


def test_health_is_real(client):
    h = client.get("/api/health").json()
    assert h["database"] is True and h["demo_mode"] is True and h["google_login"] is False


def test_auth_required(client):
    assert client.get("/api/dashboard").status_code == 401
    assert client.get("/api/dashboard", headers={"Authorization": "Bearer junk"}).status_code == 401


def test_teacher_dashboard(client):
    d = client.get("/api/dashboard", headers=login(client, "teacher")).json()
    assert d["role"] == "teacher" and len(d["courses"]) == 3
    assert all(c["students"] == 12 for c in d["courses"])
    assert d["at_risk"], "demo data should contain at least one at-risk student"


def test_student_dashboard(client):
    d = client.get("/api/dashboard", headers=login(client, "student")).json()
    assert d["role"] == "student" and len(d["scores"]) == 3
    assert all(i["status"] == "pending" for i in d["due_soon"])


def test_students_cannot_see_rosters_or_others(client):
    h = login(client, "student")
    cid = client.get("/api/courses", headers=h).json()[0]["id"]
    assert client.get(f"/api/courses/{cid}/students", headers=h).status_code == 403
    th = login(client, "teacher")
    other = client.get(f"/api/courses/{cid}/students", headers=th).json()[0]["id"]
    me = client.get("/api/me", headers=h).json()["id"]
    if other != me:
        assert client.get(f"/api/courses/{cid}/students/{other}", headers=h).status_code == 403
    assert client.get(f"/api/courses/{cid}/students/{me}", headers=h).status_code == 200


def test_csv_report(client):
    h = login(client, "teacher")
    cid = client.get("/api/courses", headers=h).json()[0]["id"]
    r = client.get(f"/api/reports/{cid}.csv", headers=h)
    assert r.status_code == 200 and r.text.startswith("Student,Email,Score")
    assert len(r.text.strip().splitlines()) == 13


def test_ask_finds_answer_with_source(client):
    r = client.post("/api/ask", json={"question": "What is the late submission policy?"}, headers=login(client, "student")).json()
    assert "10%" in r["answer"] and r["sources"][0]["title"] == "Late submission policy"


def test_ask_refuses_when_not_in_material(client):
    r = client.post("/api/ask", json={"question": "Who won the football world cup?"}, headers=login(client, "student")).json()
    assert r["mode"] == "none" and r["sources"] == []


def test_reminders_fire_once(client):
    from classroom import db as dbm, reminders
    with dbm.SessionLocal() as db:
        first = reminders.run_cycle(db, notify=lambda u, t: None)
        second = reminders.run_cycle(db, notify=lambda u, t: None)
    assert first > 0 and second == 0


def test_reminder_prefs_validated(client):
    h = login(client, "student")
    assert client.put("/api/me/reminders", json={"remind_hours": [500]}, headers=h).status_code == 422
    assert client.put("/api/me/reminders", json={"remind_hours": [2, 24]}, headers=h).json()["remind_hours"] == [24, 2]
