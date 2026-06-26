"""initial schema

Revision ID: 001
Revises:
Create Date: 2026-06-26
"""
from alembic import op
import sqlalchemy as sa

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "predictions",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("request_id", sa.String(), index=True),
        sa.Column("input_text", sa.Text()),
        sa.Column("prediction", sa.String()),
        sa.Column("confidence", sa.Float()),
        sa.Column("processing_time_ms", sa.Float()),
        sa.Column("status", sa.String(), server_default="queued"),
        sa.Column("queued_at", sa.DateTime()),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime()),
    )


def downgrade():
    op.drop_table("predictions")
