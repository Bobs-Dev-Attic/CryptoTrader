"""baseline — full schema as of Alembic adoption

Creates every table from the application's SQLAlchemy metadata. Using
``create_all`` (rather than hand-written ``op.create_table`` calls) guarantees
the baseline matches the models exactly with no transcription drift, and its
``checkfirst`` makes it a safe no-op on the pre-existing production database
(which was built by the old ``create_all`` + ``_ensure_columns`` path and is
stamped to this revision instead of re-running it).

Every schema change AFTER this point must be a real migration (``op.add_column``
etc.), not an entry in the legacy ``_ADDED_COLUMNS`` list.

Revision ID: 0001_baseline
Revises:
Create Date: 2026-07-23
"""
from alembic import op

from app.database import Base
from app import models  # noqa: F401  (populate Base.metadata)

revision = "0001_baseline"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    Base.metadata.create_all(bind=op.get_bind(), checkfirst=True)


def downgrade() -> None:
    Base.metadata.drop_all(bind=op.get_bind())
