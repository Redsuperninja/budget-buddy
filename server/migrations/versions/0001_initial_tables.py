"""Initial tables

Revision ID: 0001
Revises:
Create Date: 2026-10-02 15:45:18.632527

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "accounts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column(
            "kind",
            sa.Enum(
                "checking",
                "savings",
                "brokerage",
                name="account_kind",
                native_enum=False,
                create_constraint=True,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column("institution", sa.String(length=100), nullable=True),
        sa.Column("last4", sa.String(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_accounts")),
    )
    op.create_table(
        "categories",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column(
            "group",
            sa.Enum(
                "needs",
                "wants",
                "savings",
                "income",
                name="category_group",
                native_enum=False,
                create_constraint=True,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column("budget_cents", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_categories")),
        sa.UniqueConstraint("name", name=op.f("uq_categories_name")),
    )
    op.create_table(
        "devices",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("token_hash", sa.String(length=128), nullable=False),
        sa.Column(
            "paired_at",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column("last_sync_at", sa.DateTime(), nullable=True),
        sa.Column("revoked", sa.Boolean(), server_default="0", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_devices")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_devices_token_hash")),
    )
    op.create_table(
        "paychecks",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("pay_date", sa.Date(), nullable=False),
        sa.Column("employer", sa.String(length=200), nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=True),
        sa.Column("gross_cents", sa.Integer(), nullable=False),
        sa.Column("federal_tax_cents", sa.Integer(), server_default="0", nullable=False),
        sa.Column("state_tax_cents", sa.Integer(), server_default="0", nullable=False),
        sa.Column("social_security_cents", sa.Integer(), server_default="0", nullable=False),
        sa.Column("medicare_cents", sa.Integer(), server_default="0", nullable=False),
        sa.Column("retirement_cents", sa.Integer(), server_default="0", nullable=False),
        sa.Column("hsa_cents", sa.Integer(), server_default="0", nullable=False),
        sa.Column("other_deductions_cents", sa.Integer(), server_default="0", nullable=False),
        sa.Column("net_cents", sa.Integer(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["account_id"],
            ["accounts.id"],
            name=op.f("fk_paychecks_account_id_accounts"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_paychecks")),
    )
    with op.batch_alter_table("paychecks", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_paychecks_pay_date"), ["pay_date"], unique=False)

    op.create_table(
        "stock_lots",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=True),
        sa.Column("symbol", sa.String(length=16), nullable=False),
        sa.Column("shares_micro", sa.Integer(), nullable=False),
        sa.Column("acquired_on", sa.Date(), nullable=False),
        sa.Column("cost_basis_cents", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["account_id"],
            ["accounts.id"],
            name=op.f("fk_stock_lots_account_id_accounts"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_stock_lots")),
    )
    with op.batch_alter_table("stock_lots", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_stock_lots_symbol"), ["symbol"], unique=False)

    op.create_table(
        "transactions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("amount_cents", sa.Integer(), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=False),
        sa.Column("category_id", sa.Integer(), nullable=True),
        sa.Column(
            "source",
            sa.Enum(
                "csv",
                "manual",
                "receipt",
                name="transaction_source",
                native_enum=False,
                create_constraint=True,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["account_id"], ["accounts.id"], name=op.f("fk_transactions_account_id_accounts")
        ),
        sa.ForeignKeyConstraint(
            ["category_id"],
            ["categories.id"],
            name=op.f("fk_transactions_category_id_categories"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_transactions")),
    )
    with op.batch_alter_table("transactions", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_transactions_account_id"), ["account_id"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_transactions_category_id"), ["category_id"], unique=False
        )
        batch_op.create_index(batch_op.f("ix_transactions_date"), ["date"], unique=False)

    op.create_table(
        "receipts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("merchant", sa.String(length=200), nullable=False),
        sa.Column("total_cents", sa.Integer(), nullable=False),
        sa.Column("category_id", sa.Integer(), nullable=True),
        sa.Column("transaction_id", sa.Integer(), nullable=True),
        sa.Column("image_path", sa.String(), nullable=True),
        sa.Column("tax_deductible", sa.Boolean(), server_default="0", nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["category_id"],
            ["categories.id"],
            name=op.f("fk_receipts_category_id_categories"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["transaction_id"],
            ["transactions.id"],
            name=op.f("fk_receipts_transaction_id_transactions"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_receipts")),
    )
    with op.batch_alter_table("receipts", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_receipts_date"), ["date"], unique=False)

    op.create_table(
        "stock_sales",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("lot_id", sa.Integer(), nullable=False),
        sa.Column("sold_on", sa.Date(), nullable=False),
        sa.Column("shares_micro", sa.Integer(), nullable=False),
        sa.Column("proceeds_cents", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["lot_id"], ["stock_lots.id"], name=op.f("fk_stock_sales_lot_id_stock_lots")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_stock_sales")),
    )
    with op.batch_alter_table("stock_sales", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_stock_sales_lot_id"), ["lot_id"], unique=False)

    op.create_table(
        "deductions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tax_year", sa.Integer(), nullable=False),
        sa.Column(
            "kind",
            sa.Enum(
                "medical",
                "education",
                "student_loan_interest",
                "home_office",
                "mortgage_interest",
                "property_tax",
                "state_local_tax",
                "hsa",
                "ira",
                "childcare",
                "other",
                name="deduction_kind",
                native_enum=False,
                create_constraint=True,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column("description", sa.String(length=200), nullable=True),
        sa.Column("date", sa.Date(), nullable=True),
        sa.Column("amount_cents", sa.Integer(), nullable=False),
        sa.Column("receipt_id", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["receipt_id"],
            ["receipts.id"],
            name=op.f("fk_deductions_receipt_id_receipts"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_deductions")),
    )
    with op.batch_alter_table("deductions", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_deductions_tax_year"), ["tax_year"], unique=False)

    op.create_table(
        "donations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("organization", sa.String(length=200), nullable=False),
        sa.Column("amount_cents", sa.Integer(), nullable=False),
        sa.Column(
            "kind",
            sa.Enum(
                "cash",
                "goods",
                name="donation_kind",
                native_enum=False,
                create_constraint=True,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column("receipt_id", sa.Integer(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["receipt_id"],
            ["receipts.id"],
            name=op.f("fk_donations_receipt_id_receipts"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_donations")),
    )
    with op.batch_alter_table("donations", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_donations_date"), ["date"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("donations", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_donations_date"))

    op.drop_table("donations")
    with op.batch_alter_table("deductions", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_deductions_tax_year"))

    op.drop_table("deductions")
    with op.batch_alter_table("stock_sales", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_stock_sales_lot_id"))

    op.drop_table("stock_sales")
    with op.batch_alter_table("receipts", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_receipts_date"))

    op.drop_table("receipts")
    with op.batch_alter_table("transactions", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_transactions_date"))
        batch_op.drop_index(batch_op.f("ix_transactions_category_id"))
        batch_op.drop_index(batch_op.f("ix_transactions_account_id"))

    op.drop_table("transactions")
    with op.batch_alter_table("stock_lots", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_stock_lots_symbol"))

    op.drop_table("stock_lots")
    with op.batch_alter_table("paychecks", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_paychecks_pay_date"))

    op.drop_table("paychecks")
    op.drop_table("devices")
    op.drop_table("categories")
    op.drop_table("accounts")
