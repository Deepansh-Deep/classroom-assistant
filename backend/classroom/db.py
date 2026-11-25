"""Database models. Portable types only, so the same code runs on SQLite (default) and PostgreSQL."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, String, Text, UniqueConstraint, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship, sessionmaker
from sqlalchemy.types import TypeDecorator

from .config import get_settings


def now() -> datetime:
    return datetime.now(timezone.utc)


def new_id() -> str:
    return uuid.uuid4().hex


class UTCDateTime(TypeDecorator):
    """SQLite drops tzinfo. Store UTC and always hand back aware datetimes."""
    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is not None and value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value

    def process_result_value(self, value, dialect):
        if value is not None and value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20), default="student")  # teacher | student
    google_id: Mapped[Optional[str]] = mapped_column(String(64), unique=True)
    avatar_url: Mapped[Optional[str]] = mapped_column(String(500))
    refresh_token_enc: Mapped[Optional[str]] = mapped_column(Text)  # Fernet-encrypted Google refresh token
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    remind_hours: Mapped[list] = mapped_column(JSON, default=lambda: [48, 24, 2])
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=now)


class Course(Base):
    __tablename__ = "courses"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    external_id: Mapped[str] = mapped_column(String(64), unique=True)
    name: Mapped[str] = mapped_column(String(255))
    section: Mapped[Optional[str]] = mapped_column(String(255))
    description: Mapped[Optional[str]] = mapped_column(Text)
    synced_at: Mapped[Optional[datetime]] = mapped_column(UTCDateTime)
    enrollments = relationship("Enrollment", back_populates="course", cascade="all, delete-orphan")
    assignments = relationship("Assignment", back_populates="course", cascade="all, delete-orphan", order_by="Assignment.due_at")
    posts = relationship("Post", back_populates="course", cascade="all, delete-orphan")


class Enrollment(Base):
    __tablename__ = "enrollments"
    __table_args__ = (UniqueConstraint("user_id", "course_id"),)
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    course_id: Mapped[str] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"))
    role: Mapped[str] = mapped_column(String(20))
    user = relationship("User")
    course = relationship("Course", back_populates="enrollments")


class Assignment(Base):
    __tablename__ = "assignments"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    external_id: Mapped[str] = mapped_column(String(64), unique=True)
    course_id: Mapped[str] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(500))
    description: Mapped[Optional[str]] = mapped_column(Text)
    max_points: Mapped[Optional[float]] = mapped_column(Float)
    due_at: Mapped[Optional[datetime]] = mapped_column(UTCDateTime, index=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=now)
    course = relationship("Course", back_populates="assignments")
    submissions = relationship("Submission", back_populates="assignment", cascade="all, delete-orphan")


class Submission(Base):
    __tablename__ = "submissions"
    __table_args__ = (UniqueConstraint("assignment_id", "student_id"),)
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    assignment_id: Mapped[str] = mapped_column(ForeignKey("assignments.id", ondelete="CASCADE"), index=True)
    student_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    state: Mapped[str] = mapped_column(String(20), default="ASSIGNED")  # ASSIGNED | TURNED_IN | RETURNED
    submitted_at: Mapped[Optional[datetime]] = mapped_column(UTCDateTime)
    grade: Mapped[Optional[float]] = mapped_column(Float)
    assignment = relationship("Assignment", back_populates="submissions")
    student = relationship("User")

    @property
    def done(self) -> bool:
        return self.state in ("TURNED_IN", "RETURNED")

    @property
    def late(self) -> bool:
        due = self.assignment.due_at
        return bool(due and self.submitted_at and self.submitted_at > due)


class Post(Base):
    """Announcements and course materials: the text Q&A searches over."""
    __tablename__ = "posts"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    external_id: Mapped[str] = mapped_column(String(64), unique=True)
    course_id: Mapped[str] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(20), default="announcement")  # announcement | material
    title: Mapped[Optional[str]] = mapped_column(String(500))
    text: Mapped[str] = mapped_column(Text)
    posted_at: Mapped[datetime] = mapped_column(UTCDateTime, default=now)
    course = relationship("Course", back_populates="posts")


class ReminderLog(Base):
    """Which reminders were already sent, so each one fires exactly once."""
    __tablename__ = "reminder_log"
    __table_args__ = (UniqueConstraint("user_id", "assignment_id", "kind"),)
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    assignment_id: Mapped[str] = mapped_column(ForeignKey("assignments.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(String(20))  # "48h" | "24h" | "2h" | "overdue"
    sent_at: Mapped[datetime] = mapped_column(UTCDateTime, default=now)


class Meta(Base):
    __tablename__ = "meta"
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(Text)


_engine = None
SessionLocal: sessionmaker | None = None


def init_engine(url: str | None = None):
    global _engine, SessionLocal
    url = url or get_settings().database_url
    args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    _engine = create_engine(url, connect_args=args, pool_pre_ping=True)
    if url.startswith("sqlite"):
        @event.listens_for(_engine, "connect")
        def _fk(dbapi_conn, _):  # SQLite ignores ON DELETE CASCADE unless asked
            dbapi_conn.execute("PRAGMA foreign_keys=ON")
    Base.metadata.create_all(_engine)
    SessionLocal = sessionmaker(_engine, expire_on_commit=False)
    return _engine


def get_db():
    assert SessionLocal is not None, "init_engine() not called"
    with SessionLocal() as db:
        yield db


def ping(db: Session) -> bool:
    from sqlalchemy import text
    try:
        db.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
