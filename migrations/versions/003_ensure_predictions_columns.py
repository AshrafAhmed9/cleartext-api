"""ensure all predictions columns exist

Revision ID: 003
Revises: 002
Create Date: 2026-07-09
"""
from alembic import op

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None

_COLUMNS = [
    ("request_id", "VARCHAR"),
    ("input_text", "TEXT"),
    ("prediction", "VARCHAR"),
    ("confidence", "FLOAT"),
    ("model_version", "VARCHAR"),
    ("processing_time_ms", "FLOAT"),
    ("status", "VARCHAR DEFAULT 'queued'"),
    ("queued_at", "TIMESTAMP"),
    ("started_at", "TIMESTAMP"),
    ("created_at", "TIMESTAMP"),
]


def upgrade():
    for name, ddl_type in _COLUMNS:
        op.execute(f"ALTER TABLE predictions ADD COLUMN IF NOT EXISTS {name} {ddl_type}")
    op.execute("CREATE INDEX IF NOT EXISTS ix_predictions_request_id ON predictions (request_id)")


def downgrade():
    pass
