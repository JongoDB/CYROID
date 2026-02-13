"""merge vm_environment and vm_networks heads

Revision ID: a1b2merge0001
Revises: m1n2i3c4r5a6, y4z5a6b7c8d9
Create Date: 2026-02-13

"""
from typing import Sequence, Union


# revision identifiers, used by Alembic.
revision: str = 'a1b2merge0001'
down_revision: Union[str, Sequence[str]] = (
    'm1n2i3c4r5a6',
    'y4z5a6b7c8d9',
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
