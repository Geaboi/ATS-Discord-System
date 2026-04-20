"""Add ollama_model and ollama_scoring_model to app_settings

Revision ID: 004
Revises: 003
Create Date: 2026-04-20 00:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("app_settings", sa.Column("ollama_model", sa.String(), nullable=True))
    op.add_column("app_settings", sa.Column("ollama_scoring_model", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("app_settings", "ollama_scoring_model")
    op.drop_column("app_settings", "ollama_model")
