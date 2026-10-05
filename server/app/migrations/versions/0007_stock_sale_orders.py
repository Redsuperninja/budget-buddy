"""Stock sales as entered (roadmap #12)

A sale you enter (symbol, date, shares, money received) can use shares from several purchase
lots, so it's now its own row in ``stock_sale_orders``. The existing ``stock_sales`` rows become
the per-lot pieces of an order and point at it with ``order_id``.

Any ``stock_sales`` rows that already exist (there's no way to add them before this version, but
just in case) each become an order of their own, so nothing is lost.

Only ``stock_sales`` is rebuilt (SQLite can't add a NOT NULL foreign key column in place). No
other table points at it, so the rebuild can't trigger anyone's ``ON DELETE`` rules.

Revision ID: 0007
Revises: 0006
Create Date: 2026-10-05 12:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _stock_sales(order_id: str | None) -> sa.Table:
    """A frozen copy of ``stock_sales`` for the table rebuilds, so they don't need to read the
    live table's layout (which ``alembic upgrade --sql`` can't do).

    ``order_id``: ``None`` = no such column yet, ``"nullable"`` = added but not filled in,
    ``"final"`` = NOT NULL with its foreign key and index (this revision's end state).
    """
    columns: list = [
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
        sa.CheckConstraint("proceeds_cents >= 0", name="ck_stock_sales_proceeds_not_negative"),
        sa.CheckConstraint("shares_micro > 0", name="ck_stock_sales_shares_positive"),
        sa.ForeignKeyConstraint(
            ["lot_id"], ["stock_lots.id"], name="fk_stock_sales_lot_id_stock_lots"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_stock_sales"),
        sa.Index("ix_stock_sales_lot_id", "lot_id"),
    ]
    if order_id is not None:
        columns.append(sa.Column("order_id", sa.Integer(), nullable=order_id == "nullable"))
    if order_id == "final":
        columns += [
            sa.ForeignKeyConstraint(
                ["order_id"],
                ["stock_sale_orders.id"],
                name="fk_stock_sales_order_id_stock_sale_orders",
                ondelete="CASCADE",
            ),
            sa.Index("ix_stock_sales_order_id", "order_id"),
        ]
    return sa.Table("stock_sales", sa.MetaData(), *columns)


def upgrade() -> None:
    op.create_table(
        "stock_sale_orders",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=True),
        sa.Column("symbol", sa.String(length=16), nullable=False),
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
        sa.CheckConstraint(
            "proceeds_cents >= 0", name=op.f("ck_stock_sale_orders_proceeds_not_negative")
        ),
        sa.CheckConstraint("shares_micro > 0", name=op.f("ck_stock_sale_orders_shares_positive")),
        sa.ForeignKeyConstraint(
            ["account_id"],
            ["accounts.id"],
            name=op.f("fk_stock_sale_orders_account_id_accounts"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_stock_sale_orders")),
    )
    with op.batch_alter_table("stock_sale_orders", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_stock_sale_orders_symbol"), ["symbol"], unique=False)

    with op.batch_alter_table("stock_sales", copy_from=_stock_sales(None)) as batch_op:
        batch_op.add_column(sa.Column("order_id", sa.Integer(), nullable=True))

    # One order per existing piece, copying the account and symbol from its lot. The new table
    # is empty, so each order simply reuses its piece's id. Set-based statements (no reading rows
    # back into Python), so `alembic upgrade --sql` prints a working script too.
    op.execute(
        "INSERT INTO stock_sale_orders "
        "(id, account_id, symbol, sold_on, shares_micro, proceeds_cents) "
        "SELECT s.id, l.account_id, l.symbol, s.sold_on, s.shares_micro, s.proceeds_cents "
        "FROM stock_sales s JOIN stock_lots l ON l.id = s.lot_id"
    )
    op.execute("UPDATE stock_sales SET order_id = id")

    with op.batch_alter_table("stock_sales", copy_from=_stock_sales("nullable")) as batch_op:
        batch_op.alter_column("order_id", existing_type=sa.Integer(), nullable=False)
        batch_op.create_foreign_key(
            batch_op.f("fk_stock_sales_order_id_stock_sale_orders"),
            "stock_sale_orders",
            ["order_id"],
            ["id"],
            ondelete="CASCADE",
        )
        batch_op.create_index(batch_op.f("ix_stock_sales_order_id"), ["order_id"], unique=False)


def downgrade() -> None:
    """Drop ``stock_sale_orders`` and ``stock_sales.order_id``.

    A sale that used several lots is flattened into its per-lot ``stock_sales`` rows: each keeps
    its lot, date, shares, and share of the proceeds, but which rows belonged to one sale (and the
    sale's account) is lost.
    """
    with op.batch_alter_table("stock_sales", copy_from=_stock_sales("final")) as batch_op:
        batch_op.drop_index(batch_op.f("ix_stock_sales_order_id"))
        batch_op.drop_constraint(
            batch_op.f("fk_stock_sales_order_id_stock_sale_orders"), type_="foreignkey"
        )
        batch_op.drop_column("order_id")

    with op.batch_alter_table("stock_sale_orders", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_stock_sale_orders_symbol"))
    op.drop_table("stock_sale_orders")
