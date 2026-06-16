"""Evolution API migration: rename phone_number_id → instance_name, add instance_apikey.

Revision ID: 0003
Revises: 0002
Create Date: 2026-06-15
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Rename column: phone_number_id → instance_name
    op.alter_column("businesses", "phone_number_id", new_column_name="instance_name")

    # 2. Add instance_apikey (nullable initially)
    op.add_column("businesses", sa.Column("instance_apikey", sa.String(), nullable=True))

    # 3. Backfill: set 'MIGRATE-ME' for existing rows
    op.execute("UPDATE businesses SET instance_apikey = 'MIGRATE-ME' WHERE instance_apikey IS NULL")

    # 4. Set NOT NULL on instance_apikey
    op.alter_column("businesses", "instance_apikey", nullable=False)


def downgrade() -> None:
    # 4. Allow NULL on instance_apikey
    op.alter_column("businesses", "instance_apikey", nullable=True)

    # 3. No backfill reversal needed

    # 2. Drop instance_apikey
    op.drop_column("businesses", "instance_apikey")

    # 1. Rename back: instance_name → phone_number_id
    op.alter_column("businesses", "instance_name", new_column_name="phone_number_id")
