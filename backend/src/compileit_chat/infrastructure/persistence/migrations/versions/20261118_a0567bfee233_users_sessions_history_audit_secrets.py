"""Initial schema: users, login sessions and events, chat history, API call log, secrets.

Revision ID: a0567bfee233
Revises:
Create Date: 2026-11-18 10:33:47.607506
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a0567bfee233"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "api_calls",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.String(length=32), nullable=False),
        sa.Column("conversation_id", sa.String(length=128), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("answer", sa.Text(), nullable=False),
        sa.Column("sources", sa.JSON(), nullable=False),
        sa.Column("tools", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("first_token_ms", sa.Integer(), nullable=True),
        sa.Column("total_ms", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("api_calls", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_api_calls_conversation_id"), ["conversation_id"], unique=False
        )
        batch_op.create_index(batch_op.f("ix_api_calls_created_at"), ["created_at"], unique=False)
        batch_op.create_index(batch_op.f("ix_api_calls_status"), ["status"], unique=False)
        batch_op.create_index(batch_op.f("ix_api_calls_user_id"), ["user_id"], unique=False)

    op.create_table(
        "login_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("username", sa.String(length=64), nullable=False),
        sa.Column("succeeded", sa.Boolean(), nullable=False),
        sa.Column("client", sa.String(length=64), nullable=True),
        sa.Column(
            "at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("login_events", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_login_events_at"), ["at"], unique=False)
        batch_op.create_index(batch_op.f("ix_login_events_username"), ["username"], unique=False)

    op.create_table(
        "secrets",
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("ciphertext", sa.LargeBinary(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("name"),
    )
    op.create_table(
        "users",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("username", sa.String(length=64), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("username"),
    )
    op.create_table(
        "auth_sessions",
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=32), nullable=False),
        sa.Column(
            "expires_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("token_hash"),
    )
    with op.batch_alter_table("auth_sessions", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_auth_sessions_expires_at"), ["expires_at"], unique=False
        )
        batch_op.create_index(batch_op.f("ix_auth_sessions_user_id"), ["user_id"], unique=False)

    op.create_table(
        "conversations",
        sa.Column("id", sa.String(length=128), nullable=False),
        sa.Column("user_id", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("conversations", schema=None) as batch_op:
        batch_op.create_index(
            "ix_conversations_user_updated", ["user_id", "updated_at"], unique=False
        )

    op.create_table(
        "messages",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("conversation_id", sa.String(length=128), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("sources", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("messages", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_messages_conversation_id"), ["conversation_id"], unique=False
        )


def downgrade() -> None:
    with op.batch_alter_table("messages", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_messages_conversation_id"))

    op.drop_table("messages")
    with op.batch_alter_table("conversations", schema=None) as batch_op:
        batch_op.drop_index("ix_conversations_user_updated")

    op.drop_table("conversations")
    with op.batch_alter_table("auth_sessions", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_auth_sessions_user_id"))
        batch_op.drop_index(batch_op.f("ix_auth_sessions_expires_at"))

    op.drop_table("auth_sessions")
    op.drop_table("users")
    op.drop_table("secrets")
    with op.batch_alter_table("login_events", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_login_events_username"))
        batch_op.drop_index(batch_op.f("ix_login_events_at"))

    op.drop_table("login_events")
    with op.batch_alter_table("api_calls", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_api_calls_user_id"))
        batch_op.drop_index(batch_op.f("ix_api_calls_status"))
        batch_op.drop_index(batch_op.f("ix_api_calls_created_at"))
        batch_op.drop_index(batch_op.f("ix_api_calls_conversation_id"))

    op.drop_table("api_calls")
