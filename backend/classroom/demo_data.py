"""A realistic, fictional classroom so the app can be tried without a Google account.

Dates are relative to the moment of seeding, so the demo always has work that is
overdue, due this week and due later. Student behaviour follows four profiles
(consistent, average, last-minute, struggling) so analytics have something real to find.
"""
from __future__ import annotations

import random
from datetime import timedelta

from sqlalchemy import delete
from sqlalchemy.orm import Session

from .db import Assignment, Base, Course, Enrollment, Meta, Post, Submission, User, now

TEACHER = ("Ananya Rao", "ananya.rao@demo.classroom")
STUDENTS = [  # (name, profile)
    ("Aarav Mehta", "consistent"), ("Diya Banerjee", "consistent"), ("Kabir Singh", "average"),
    ("Ishita Ghosh", "average"), ("Rohan Das", "last_minute"), ("Meera Iyer", "consistent"),
    ("Arjun Nair", "struggling"), ("Sneha Kulkarni", "average"), ("Vivaan Joshi", "last_minute"),
    ("Tanya Paul", "struggling"), ("Nikhil Verma", "average"), ("Riya Sen", "consistent"),
]
DEMO_STUDENT = "Rohan Das"  # the student you log in as: decent but often late, so there is advice to give

PROFILE = {  # p(submit), p(late | submit), grade mean, grade sd
    "consistent": (0.98, 0.05, 0.88, 0.06),
    "average": (0.88, 0.2, 0.72, 0.1),
    "last_minute": (0.85, 0.55, 0.7, 0.1),
    "struggling": (0.55, 0.5, 0.52, 0.12),
}

COURSES = [
    {
        "name": "Machine Learning", "section": "CSE (Data Science) · Sem 6",
        "description": "Supervised and unsupervised learning, model evaluation, and a capstone project.",
        "assignments": [
            ("Linear regression from scratch", "Implement gradient descent for linear regression in NumPy only. Plot the loss curve and compare with scikit-learn. Submit a notebook.", 20, -38),
            ("Logistic regression on the Titanic dataset", "Clean the data, engineer at least three features, report accuracy, precision and recall. Explain one false positive.", 20, -30),
            ("Decision trees and overfitting", "Train trees of depth 1 to 20, plot train vs validation accuracy and explain where overfitting starts.", 20, -22),
            ("K-means customer segmentation", "Cluster the mall customers dataset, choose k with the elbow method and silhouette score, and describe each segment in one line.", 25, -14),
            ("Mid-term quiz: evaluation metrics", "Online quiz on confusion matrix, ROC-AUC, F1 and cross-validation. 30 minutes, one attempt.", 30, -7),
            ("Neural network from scratch", "Build a two-layer network with backpropagation in NumPy and train it on MNIST. Target: 90% test accuracy.", 30, 2),
            ("Capstone proposal", "One page: problem, dataset, baseline model, evaluation metric and a week-by-week plan. Groups of up to three.", 10, 6),
            ("Capstone final report", "8 to 12 pages plus code repository and a 5-minute demo video.", 50, 20),
        ],
        "posts": [
            ("announcement", "Mid-term exam schedule", "The ML mid-term written exam is on the 14th of next month, 10:00 to 13:00 in Room 204. It covers units 1 to 4: regression, classification, trees and clustering. Calculators are allowed; phones are not."),
            ("announcement", "Late submission policy", "Late assignments lose 10% of the marks per day, up to 3 days. After 3 days the submission is not graded. If you are ill, email me a medical certificate before the deadline for an extension."),
            ("material", "Capstone project guidelines", "Capstone groups can have at most three members. Each group must use a public dataset and report a baseline before any deep model. Evaluation: proposal 10%, final report 50%, code quality 20%, demo video 20%. Plagiarism results in zero for the whole group."),
            ("announcement", "Office hours", "Office hours are on Tuesdays and Thursdays from 15:00 to 16:30 in the CSE faculty room, second floor. You can also post questions here and I will answer within a day."),
            ("material", "Recommended reading", "Primary textbook: Hands-On Machine Learning (Géron), chapters 1 to 9. For the maths, use the free Mathematics for Machine Learning book. Lecture slides are uploaded after every class."),
        ],
    },
    {
        "name": "Database Management Systems", "section": "CSE (Data Science) · Sem 6",
        "description": "Relational model, SQL, normalisation, transactions and indexing.",
        "assignments": [
            ("ER diagram for a hospital system", "Draw an ER diagram for patients, doctors, appointments and billing. Mark cardinalities and weak entities.", 15, -35),
            ("SQL joins practice set", "Solve 15 queries on the university schema using inner, left and self joins. Submit the .sql file.", 15, -24),
            ("Normalisation up to BCNF", "Normalise the given library relation to BCNF, showing each functional dependency and decomposition step.", 20, -12),
            ("Transactions and concurrency lab", "Demonstrate a lost update and a dirty read in PostgreSQL, then fix both using isolation levels.", 20, -3),
            ("Indexing performance report", "Measure query time on a 1 million row table with and without B-tree and hash indexes. Plot the results.", 25, 4),
            ("Mini project: library management DB", "Schema, seed data, 10 meaningful queries, and two stored procedures. Demo in the lab.", 40, 13),
        ],
        "posts": [
            ("announcement", "Lab rules", "DBMS lab attendance is compulsory; three absences mean you cannot sit the lab exam. Bring your own laptop with PostgreSQL 15 installed. Lab sessions are on Fridays, 10:00 to 13:00."),
            ("material", "Mini project rubric", "Mini project marks: schema design 30%, queries 30%, stored procedures 20%, viva 20%. Each student must be able to explain every query during the viva."),
            ("announcement", "Class test 2", "Class test 2 covers normalisation and transactions. It will be held in the regular lecture slot next Wednesday and carries 15 internal marks."),
        ],
    },
    {
        "name": "Software Engineering", "section": "CSE (Data Science) · Sem 6",
        "description": "Requirements, design, testing and agile delivery through a semester-long team project.",
        "assignments": [
            ("Software requirements specification", "Write an IEEE-style SRS for your team project: functional requirements, non-functional requirements and use cases.", 20, -28),
            ("UML class and sequence diagrams", "Model the core of your project with one class diagram and two sequence diagrams.", 15, -16),
            ("Unit testing assignment", "Write unit tests for the given payment module and reach 80% line coverage. Submit the coverage report.", 20, -5),
            ("Sprint 2 demo and retrospective", "Demo the working increment and submit a one-page retrospective: what went well, what didn't, one change.", 15, 1),
            ("Final project submission", "Source code, README with setup steps, test report and a 10-minute presentation.", 50, 18),
        ],
        "posts": [
            ("announcement", "Team formation", "Teams of four for the semester project must be finalised by this Friday. Send the team name, members and project idea to the class representative."),
            ("material", "Grading scheme", "Software Engineering internal marks: assignments 30%, sprint demos 20%, final project 30%, class participation 20%. The university end-semester exam is separate."),
            ("announcement", "Guest lecture on CI/CD", "A guest lecture on continuous integration and deployment with GitHub Actions is scheduled for next Monday at 14:00 in the seminar hall. Attendance counts towards participation."),
        ],
    },
]


def seed(db: Session, rng_seed: int = 7) -> None:
    rng = random.Random(rng_seed)
    t0 = now()
    for table in reversed(Base.metadata.sorted_tables):
        db.execute(delete(table))

    teacher = User(name=TEACHER[0], email=TEACHER[1], role="teacher", is_demo=True)
    db.add(teacher)
    students = []
    for name, profile in STUDENTS:
        u = User(name=name, email=name.lower().replace(" ", ".") + "@demo.classroom", role="student", is_demo=True)
        u._profile = profile  # transient, used only while seeding
        students.append(u)
        db.add(u)
    db.flush()

    for ci, spec in enumerate(COURSES):
        course = Course(external_id=f"demo-course-{ci}", name=spec["name"], section=spec["section"],
                        description=spec["description"], synced_at=t0)
        db.add(course)
        db.flush()
        db.add(Enrollment(user_id=teacher.id, course_id=course.id, role="teacher"))
        for s in students:
            db.add(Enrollment(user_id=s.id, course_id=course.id, role="student"))

        for ai, (title, desc, pts, due_days) in enumerate(spec["assignments"]):
            due = (t0 + timedelta(days=due_days)).replace(hour=23, minute=59, second=0, microsecond=0)
            a = Assignment(external_id=f"demo-a-{ci}-{ai}", course_id=course.id, title=title, description=desc,
                           max_points=pts, due_at=due, created_at=due - timedelta(days=10))
            db.add(a)
            db.flush()
            for s in students:
                p_submit, p_late, g_mu, g_sd = PROFILE[s._profile]
                sub = Submission(assignment_id=a.id, student_id=s.id, state="ASSIGNED")
                if due_days < 0 and rng.random() < p_submit:
                    late = rng.random() < p_late
                    delta = timedelta(hours=rng.uniform(2, 60)) if late else -timedelta(hours=rng.uniform(1, 72))
                    sub.submitted_at = due + delta
                    graded = due_days < -4
                    sub.state = "RETURNED" if graded else "TURNED_IN"
                    if graded:
                        g = min(1.0, max(0.2, rng.gauss(g_mu, g_sd)))
                        sub.grade = round(g * pts * (0.9 if late else 1.0), 1)
                elif 0 <= due_days <= 3 and s._profile == "consistent" and rng.random() < 0.6:
                    sub.state, sub.submitted_at = "TURNED_IN", t0 - timedelta(hours=rng.uniform(1, 30))
                db.add(sub)

        for pi, (kind, title, text) in enumerate(spec["posts"]):
            db.add(Post(external_id=f"demo-p-{ci}-{pi}", course_id=course.id, kind=kind, title=title, text=text,
                        posted_at=t0 - timedelta(days=30 - pi * 6)))

    db.merge(Meta(key="demo_seeded_at", value=t0.isoformat()))
    db.commit()


def demo_user(db: Session, role: str) -> User | None:
    from sqlalchemy import select
    if role == "teacher":
        return db.scalar(select(User).where(User.email == TEACHER[1]))
    return db.scalar(select(User).where(User.name == DEMO_STUDENT, User.is_demo.is_(True)))
