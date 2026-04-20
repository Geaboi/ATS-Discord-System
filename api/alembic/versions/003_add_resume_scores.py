"""Add resume_scores table

Revision ID: 003
Revises: 002
Create Date: 2026-04-20 00:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "resume_scores",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("resume_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("strengths", postgresql.ARRAY(sa.String()), nullable=True, server_default="{}"),
        sa.Column("weaknesses", postgresql.ARRAY(sa.String()), nullable=True, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["resume_id"], ["resumes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("resume_id", "job_id", name="uq_resume_scores_resume_job"),
    )
    op.create_index("idx_resume_scores_job_id", "resume_scores", ["job_id"])
    op.create_index("idx_resume_scores_resume_id", "resume_scores", ["resume_id"])


def downgrade() -> None:
    op.drop_index("idx_resume_scores_resume_id", "resume_scores")
    op.drop_index("idx_resume_scores_job_id", "resume_scores")
    op.drop_table("resume_scores")
