"""Add experience_level to jobs

Revision ID: 002
Revises: 001
Create Date: 2026-04-19 00:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("jobs", sa.Column("experience_level", sa.String(), nullable=True))
    op.create_index("idx_jobs_exp_level", "jobs", ["experience_level"])


def downgrade() -> None:
    op.drop_index("idx_jobs_exp_level", table_name="jobs")
    op.drop_column("jobs", "experience_level")
