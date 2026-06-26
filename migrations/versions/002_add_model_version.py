"""add model_version column

Revision ID: 002
Revises: 001
Create Date: 2026-06-26
"""
from alembic import op
import sqlalchemy as sa

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("predictions", sa.Column("model_version", sa.String(), nullable=True))


def downgrade():
    op.drop_column("predictions", "model_version")
