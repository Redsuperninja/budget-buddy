"""Paycheck lines for qualified tips and qualified overtime premium (issue #13)

Two more ``paycheck_lines.kind`` values: ``qualified_tips`` and ``qualified_overtime``. They are
pay already inside gross pay, kept so the tax summary can show them; they never change take-home.
``kind`` has a CHECK constraint listing the allowed values, so the table is rebuilt (SQLite can't
change a CHECK in place). Existing lines are copied unchanged.

Downgrading deletes lines of the two new kinds (the older list can't hold them). They never
changed take-home pay, so every paycheck still adds up.

Revision ID: 0033
Revises: 0032
Create Date: 2026-11-10 18:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0033"
down_revision: str | None = "0032"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OLD_KINDS = (
    "local_tax",
    "state_disability",
    "paid_family_leave",
    "health_fsa",
    "dependent_care_fsa",
    "employer_hsa",
    "imputed_income",
    "reimbursement",
)
NEW_KINDS = (*OLD_KINDS, "qualified_tips", "qualified_overtime")


def _kind(kinds: tuple[str, ...]) -> sa.Enum:
    return sa.Enum(
        *kinds, name="paycheck_line_kind", native_enum=False, create_constraint=True, length=32
    )


def _paycheck_lines(kinds: tuple[str, ...]) -> sa.Table:
    """A frozen copy of ``paycheck_lines`` (as 0031 made it) for the rebuild, so it doesn't need
    to read the live table's layout (which ``alembic upgrade --sql`` can't do)."""
    metadata = sa.MetaData(naming_convention={"ck": "ck_%(table_name)s_%(constraint_name)s"})
    return sa.Table(
        "paycheck_lines",
        metadata,
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("paycheck_id", sa.Integer(), nullable=False),
        sa.Column("kind", _kind(kinds), nullable=False),
        sa.Column("amount_cents", sa.Integer(), nullable=False),
        sa.Column("pre_tax_federal", sa.Boolean(), server_default="0", nullable=False),
        sa.Column("pre_tax_fica", sa.Boolean(), server_default="0", nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("amount_cents >= 0", name="amount_cents_not_negative"),
        sa.ForeignKeyConstraint(
            ["paycheck_id"],
            ["paychecks.id"],
            name="fk_paycheck_lines_paycheck_id_paychecks",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_paycheck_lines"),
        sa.Index("ix_paycheck_lines_paycheck_id", "paycheck_id"),
    )


def _change_kinds(old: tuple[str, ...], new: tuple[str, ...]) -> None:
    with op.batch_alter_table(
        "paycheck_lines", copy_from=_paycheck_lines(old), recreate="always"
    ) as batch:
        batch.alter_column("kind", existing_type=_kind(old), type_=_kind(new), nullable=False)


def upgrade() -> None:
    _change_kinds(OLD_KINDS, NEW_KINDS)


def downgrade() -> None:
    op.execute("DELETE FROM paycheck_lines WHERE kind IN ('qualified_tips', 'qualified_overtime')")
    _change_kinds(NEW_KINDS, OLD_KINDS)
