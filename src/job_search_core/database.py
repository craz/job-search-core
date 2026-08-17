"""SQLAlchemy engine, session lifecycle, and Core database readiness checks.

Core is the exclusive owner of these tables. Application code receives a
``Database`` instance rather than using a module-global session, which keeps
tests isolated and makes transaction boundaries explicit. Production URLs use
PostgreSQL through Psycopg; SQLite support exists only for fast local tests.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session, sessionmaker


class Database:
    """Own one SQLAlchemy engine and short-lived transactional sessions."""

    def __init__(self, url: str, *, engine: Engine | None = None) -> None:
        """Create an engine unless an explicitly configured test engine is supplied."""
        self.engine = engine or create_engine(url, pool_pre_ping=True)
        self._sessions = sessionmaker(bind=self.engine, expire_on_commit=False)

    @contextmanager
    def session(self) -> Iterator[Session]:
        """Commit a successful unit of work and roll back every failure."""
        session = self._sessions()
        try:
            yield session
            session.commit()
        except BaseException:
            session.rollback()
            raise
        finally:
            session.close()

    def ping(self) -> None:
        """Execute a bounded pool-level connectivity query for readiness probes."""
        with self.engine.connect() as connection:
            connection.execute(text("SELECT 1"))
