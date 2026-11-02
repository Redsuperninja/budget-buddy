"""Paycheck lines, pay period and year-to-date figures (issue #13)

Adds ``paycheck_lines`` (extra pay-stub lines such as local tax, SDI, FSA and reimbursements) and
optional ``period_start``/``period_end`` and four ``ytd_*`` columns to ``paychecks``. Nothing is
encrypted: these are amounts and kinds, like the other paycheck amounts. Existing paychecks are
unchanged (no lines, empty period and year-to-date).

Revision ID: 0031
Revises: 0030
Create Date: 2026-11-02 18:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0031"
down_revision: str | None = "0030"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

YTD_COLUMNS = (
    "ytd_gross_cents",
    "ytd_federal_tax_cents",
    "ytd_social_security_cents",
    "ytd_medicare_cents",
)
KINDS = (
    "local_tax",
    "state_disability",
    "paid_family_leave",
    "health_fsa",
    "dependent_care_fsa",
    "employer_hsa",
    "imputed_income",
    "reimbursement",
)


def upgrade() -> None:
    with op.batch_alter_table("paychecks", recreate="always") as batch:
        batch.add_column(sa.Column("period_start", sa.Date(), nullable=True))
        batch.add_column(sa.Column("period_end", sa.Date(), nullable=True))
        for column in YTD_COLUMNS:
            batch.add_column(sa.Column(column, sa.Integer(), nullable=True))
            batch.create_check_constraint(
                f"{column}_not_negative", f"{column} IS NULL OR {column} >= 0"
            )
    op.create_table(
        "paycheck_lines",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("paycheck_id", sa.Integer(), nullable=False),
        sa.Column(
            "kind",
            sa.Enum(
                *KINDS,
                name="paycheck_line_kind",
                native_enum=False,
                create_constraint=True,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column("amount_cents", sa.Integer(), nullable=False),
        sa.Column("pre_tax_federal", sa.Boolean(), server_default="0", nullable=False),
        sa.Column("pre_tax_fica", sa.Boolean(), server_default="0", nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("amount_cents >= 0", name=op.f("ck_paycheck_lines_amount_cents_not_negative")),
        sa.ForeignKeyConstraint(
            ["paycheck_id"],
            ["paychecks.id"],
            name=op.f("fk_paycheck_lines_paycheck_id_paychecks"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_paycheck_lines")),
    )
    op.create_index(op.f("ix_paycheck_lines_paycheck_id"), "paycheck_lines", ["paycheck_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_paycheck_lines_paycheck_id"), table_name="paycheck_lines")
    op.drop_table("paycheck_lines")
    with op.batch_alter_table("paychecks", recreate="always") as batch:
        for column in YTD_COLUMNS:
            batch.drop_constraint(op.f(f"ck_paychecks_{column}_not_negative"), "check")
            batch.drop_column(column)
        batch.drop_column("period_end")
        batch.drop_column("period_start")
