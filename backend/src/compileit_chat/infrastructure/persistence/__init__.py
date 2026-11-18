"""Relational persistence (SQLAlchemy 2.0, async; schema managed by Alembic migrations).

Defaults to a SQLite file. The schema is portable, so moving to e.g. PostgreSQL is a
`DATABASE_URL` change (plus the async driver), not a code change.
"""
