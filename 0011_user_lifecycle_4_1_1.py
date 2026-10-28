"""User lifecycle and optional simple passwords for 4.1.1.

Revision ID: 0011_user_lifecycle_4_1_1
Revises: 0010_core_workspace_schema_repair_4_0_4
Create Date: 2026-09-14

Adds only a soft-delete timestamp to users. Password-policy changes live in
application code and do not rewrite existing password hashes.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0011_user_lifecycle_4_1_1"
down_revision = "0010_core_workspace_schema_repair_4_0_4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "users" not in set(inspector.get_table_names()):
        return
    columns = {c["name"] for c in inspector.get_columns("users")}
    if "deleted_at" not in columns:
        op.add_column("users", sa.Column("deleted_at", sa.DateTime(), nullable=True))
    indexes = {idx["name"] for idx in sa.inspect(op.get_bind()).get_indexes("users")}
    if "ix_users_deleted_at" not in indexes:
        op.create_index("ix_users_deleted_at", "users", ["deleted_at"], unique=False)
    if "must_change_password" in {c["name"] for c in sa.inspect(op.get_bind()).get_columns("users")}:
        op.get_bind().execute(sa.text("UPDATE users SET must_change_password = :value WHERE must_change_password = :old"), {"value": False, "old": True})


def downgrade() -> None:
    # Keep deletion state on downgrade to avoid reviving intentionally removed accounts.
    pass
