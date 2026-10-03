"""Accounts, categories, transactions, paychecks, and receipts. Amounts are integer cents."""

import datetime as dt

from sqlalchemy import CheckConstraint, Date, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.crypto.fields import EncryptedString
from app.models.base import Base, TimestampMixin, str_enum
from app.models.enums import AccountKind, CategoryGroup, TransactionKind, TransactionSource


class Account(TimestampMixin, Base):
    __tablename__ = "accounts"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    kind: Mapped[AccountKind] = mapped_column(str_enum(AccountKind, "account_kind"))
    institution: Mapped[str | None] = mapped_column(String(100))
    last4: Mapped[str | None] = mapped_column(EncryptedString("accounts.last4"))
    notes: Mapped[str | None] = mapped_column(EncryptedString("accounts.notes"))


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
    kind: Mapped[TransactionKind] = mapped_column(
        str_enum(TransactionKind, "transaction_kind"),
        default=TransactionKind.NORMAL,
        server_default=TransactionKind.NORMAL.value,
    )
    # For a transfer: the matching transaction on the other account.
    transfer_pair_id: Mapped[int | None] = mapped_column(
        ForeignKey("transactions.id", ondelete="SET NULL")
    )
    notes: Mapped[str | None] = mapped_column(EncryptedString("transactions.notes"))


class Paycheck(TimestampMixin, Base):
    __tablename__ = "paychecks"
    __table_args__ = tuple(
        CheckConstraint(f"{column} >= 0", name=f"{column}_not_negative")
        for column in (
            "gross_cents",
            "federal_tax_cents",
            "state_tax_cents",
            "social_security_cents",
            "medicare_cents",
            "retirement_cents",
            "hsa_cents",
            "health_insurance_cents",
            "roth_retirement_cents",
            "other_deductions_cents",
            "net_cents",
        )
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    pay_date: Mapped[dt.date] = mapped_column(Date, index=True)
    employer: Mapped[str] = mapped_column(String(200))
    account_id: Mapped[int | None] = mapped_column(
        ForeignKey("accounts.id", ondelete="SET NULL")
    )  # where the money was deposited
    # The deposit in your bank account that this paycheck explains (roadmap #7). Its amount is
    # the net pay. One deposit can back only one paycheck.
    deposit_transaction_id: Mapped[int | None] = mapped_column(
        ForeignKey("transactions.id", ondelete="SET NULL"), index=True, unique=True
    )
    gross_cents: Mapped[int]
    federal_tax_cents: Mapped[int] = mapped_column(default=0, server_default="0")
    state_tax_cents: Mapped[int] = mapped_column(default=0, server_default="0")
    social_security_cents: Mapped[int] = mapped_column(default=0, server_default="0")
    medicare_cents: Mapped[int] = mapped_column(default=0, server_default="0")
    # Pre-tax (traditional) 401(k)/403(b)/457 contributions.
    retirement_cents: Mapped[int] = mapped_column(default=0, server_default="0")
    hsa_cents: Mapped[int] = mapped_column(default=0, server_default="0")
    # Pre-tax: Section 125 health/dental/vision premiums, FSAs, and similar benefits.
    health_insurance_cents: Mapped[int] = mapped_column(default=0, server_default="0")
    # After tax: Roth 401(k)/403(b) contributions.
    roth_retirement_cents: Mapped[int] = mapped_column(default=0, server_default="0")
    # After tax: anything else (union dues, after-tax insurance, ESPP, garnishments).
    other_deductions_cents: Mapped[int] = mapped_column(default=0, server_default="0")
    net_cents: Mapped[int]
    notes: Mapped[str | None] = mapped_column(EncryptedString("paychecks.notes"))


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
    image_path: Mapped[str | None] = mapped_column(EncryptedString("receipts.image_path"))
    tax_deductible: Mapped[bool] = mapped_column(default=False, server_default="0")
    notes: Mapped[str | None] = mapped_column(EncryptedString("receipts.notes"))
