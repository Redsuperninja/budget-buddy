"""Accounts, categories, transactions, paychecks, and receipts. Amounts are integer cents."""

import datetime as dt

from sqlalchemy import Date, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, str_enum
from app.models.enums import AccountKind, CategoryGroup, TransactionSource


class Account(TimestampMixin, Base):
    __tablename__ = "accounts"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    kind: Mapped[AccountKind] = mapped_column(str_enum(AccountKind, "account_kind"))
    institution: Mapped[str | None] = mapped_column(String(100))
    last4: Mapped[str | None] = mapped_column(String)  # encrypted in roadmap #4
    notes: Mapped[str | None] = mapped_column(Text)  # encrypted in roadmap #4


class Category(TimestampMixin, Base):
    __tablename__ = "categories"
    __table_args__ = (UniqueConstraint("name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    group: Mapped[CategoryGroup] = mapped_column(str_enum(CategoryGroup, "category_group"))
    budget_cents: Mapped[int] = mapped_column(default=0, server_default="0")


class Transaction(TimestampMixin, Base):
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), index=True)
    date: Mapped[dt.date] = mapped_column(Date, index=True)
    # Negative = money out, positive = money in.
    amount_cents: Mapped[int]
    description: Mapped[str] = mapped_column(String(500))
    category_id: Mapped[int | None] = mapped_column(
        ForeignKey("categories.id", ondelete="SET NULL"), index=True
    )
    source: Mapped[TransactionSource] = mapped_column(
        str_enum(TransactionSource, "transaction_source")
    )
    notes: Mapped[str | None] = mapped_column(Text)  # encrypted in roadmap #4


class Paycheck(TimestampMixin, Base):
    __tablename__ = "paychecks"

    id: Mapped[int] = mapped_column(primary_key=True)
    pay_date: Mapped[dt.date] = mapped_column(Date, index=True)
    employer: Mapped[str] = mapped_column(String(200))
    account_id: Mapped[int | None] = mapped_column(
        ForeignKey("accounts.id", ondelete="SET NULL")
    )  # where the money was deposited
    gross_cents: Mapped[int]
    federal_tax_cents: Mapped[int] = mapped_column(default=0, server_default="0")
    state_tax_cents: Mapped[int] = mapped_column(default=0, server_default="0")
    social_security_cents: Mapped[int] = mapped_column(default=0, server_default="0")
    medicare_cents: Mapped[int] = mapped_column(default=0, server_default="0")
    retirement_cents: Mapped[int] = mapped_column(default=0, server_default="0")
    hsa_cents: Mapped[int] = mapped_column(default=0, server_default="0")
    other_deductions_cents: Mapped[int] = mapped_column(default=0, server_default="0")
    net_cents: Mapped[int]
    notes: Mapped[str | None] = mapped_column(Text)  # encrypted in roadmap #4


class Receipt(TimestampMixin, Base):
    __tablename__ = "receipts"

    id: Mapped[int] = mapped_column(primary_key=True)
    date: Mapped[dt.date] = mapped_column(Date, index=True)
    merchant: Mapped[str] = mapped_column(String(200))
    total_cents: Mapped[int]
    category_id: Mapped[int | None] = mapped_column(
        ForeignKey("categories.id", ondelete="SET NULL")
    )
    transaction_id: Mapped[int | None] = mapped_column(
        ForeignKey("transactions.id", ondelete="SET NULL")
    )
    image_path: Mapped[str | None] = mapped_column(String)  # encrypted in roadmap #4
    tax_deductible: Mapped[bool] = mapped_column(default=False, server_default="0")
    notes: Mapped[str | None] = mapped_column(Text)  # encrypted in roadmap #4
