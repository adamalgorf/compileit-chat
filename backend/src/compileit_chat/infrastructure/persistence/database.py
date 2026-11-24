"""Engine, sessions and schema migrations."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import TYPE_CHECKING, Any

from alembic import command
from alembic.config import Config
from sqlalchemy import event
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncEngine

MIGRATIONS_DIR = Path(__file__).with_name("migrations")


class Database:
    """The async SQLAlchemy engine and session factory for one database URL."""

    def __init__(self, url: str) -> None:
        self.url = url
        _ensure_sqlite_directory(url)
        self.engine: AsyncEngine = create_async_engine(url)
        if make_url(url).get_backend_name() == "sqlite":
            # SQLite ignores foreign keys (and so ON DELETE CASCADE) unless asked per connection.
            event.listen(self.engine.sync_engine, "connect", _enable_sqlite_foreign_keys)
        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)

    def session(self) -> AsyncSession:
        return self.sessions()

    async def upgrade(self) -> None:
        """Apply pending Alembic migrations. Alembic's async env runs its own event loop,
        hence a worker thread."""
        await asyncio.to_thread(command.upgrade, alembic_config(self.url), "head")

    async def dispose(self) -> None:
        await self.engine.dispose()


def alembic_config(url: str) -> Config:
    """Alembic configuration for running the migrations against `url`."""
    config = Config()
    config.set_main_option("script_location", str(MIGRATIONS_DIR))
    config.set_main_option("sqlalchemy.url", url)
    return config


def _ensure_sqlite_directory(url: str) -> None:
    parsed = make_url(url)
    if parsed.get_backend_name() == "sqlite" and parsed.database not in (None, "", ":memory:"):
        Path(parsed.database).parent.mkdir(parents=True, exist_ok=True)


def _enable_sqlite_foreign_keys(connection: Any, _record: Any) -> None:
    cursor = connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()
