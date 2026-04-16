from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import Boolean, DateTime, Integer, String, Text, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False, index=True)
    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    license_type: Mapped[Optional[str]] = mapped_column(String(20), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False, default=datetime.utcnow)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False, default=datetime.utcnow, index=True)
    actor: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    target: Mapped[str] = mapped_column(String(320), nullable=False, index=True)
    details: Mapped[str] = mapped_column(Text, nullable=False)


@dataclass(frozen=True)
class Database:
    """Small helper wrapper for SQLAlchemy engine + session factory."""

    engine: Any
    session_factory: sessionmaker[Session]

    def session(self) -> Session:
        """Create a new session. Prefer `with db.session() as s:` usage."""

        return self.session_factory()


def create_sqlite_db(db_url: str) -> Database:
    """Create SQLAlchemy engine/session for SQLite."""

    engine = create_engine(db_url, echo=False, future=True)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    return Database(engine=engine, session_factory=session_factory)


def init_db(db: Database) -> None:
    """Create tables if missing."""

    Base.metadata.create_all(db.engine)


def user_count(db: Database) -> int:
    """Return total users count."""

    with db.session() as session:
        return len(list(session.execute(select(User.id)).scalars().all()))
