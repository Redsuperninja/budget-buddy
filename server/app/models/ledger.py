"""Accounts, categories, transactions, paychecks, and receipts. Amounts are integer cents."""

import datetime as dt

from sqlalchemy import CheckConstraint, Date, ForeignKey, String, Text, UniqueConstraint
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
    __table_args__ = (
        UniqueConstraint("name"),
        CheckConstraint(
            "budget_percent_bp IS NULL OR budget_percent_bp BETWEEN 1 AND 10000",
            name="budget_percent_range",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    group: Mapped[CategoryGroup] = mapped_column(str_enum(CategoryGroup, "category_group"))
    budget_cents: Mapped[int] = mapped_column(default=0, server_default="0")
    # A budget as a share of monthly income, in basis points (1500 = 15%). When set, it replaces
    # ``budget_cents``; see app/services/budget_plan.py for which income it's a share of.
    budget_percent_bp: Mapped[int | None]


class BudgetPlan(TimestampMixin, Base):
    """Budget settings: one row (id 1), made when first saved."""

    __tablename__ = "budget_plan"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Take-home pay you plan on each month. Percentage budgets are shares of it; without it, they
    # are shares of the month's actual income.
    planned_income_cents: Mapped[int | None]


class CategoryRule(TimestampMixin, Base):
    """Auto-categorization: a transaction whose description contains ``pattern`` (ignoring upper
    and lower case) gets ``category_id``. See app/services/category_rules.py for which rule wins."""

    __tablename__ = "category_rules"
    __table_args__ = (UniqueConstraint("pattern"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    pattern: Mapped[str] = mapped_column(String(100))
    category_id: Mapped[int] = mapped_column(
        ForeignKey("categories.id", ondelete="CASCADE"), index=True
    )


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
    # CSV import only: a hash of (account, date, amount, description, occurrence) so importing
    # an overlapping statement again doesn't add the same rows twice. See services/csv_import.py.
    import_fingerprint: Mapped[str | None] = mapped_column(String(64), unique=True, index=True)


class CsvImportMapping(TimestampMixin, Base):
    """The column mapping saved for an account, so its next CSV import is one click."""

    __tablename__ = "csv_import_mappings"

    account_id: Mapped[int] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"), primary_key=True
    )
    mapping: Mapped[str] = mapped_column(Text)  # JSON, see app.schemas.csv_import.CsvMapping


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
    # The photo's ID in the encrypted file store (``<data_dir>/receipts/<id>.bbf``), not a path.
    image_path: Mapped[str | None] = mapped_column(EncryptedString("receipts.image_path"))
    tax_deductible: Mapped[bool] = mapped_column(default=False, server_default="0")
    notes: Mapped[str | None] = mapped_column(EncryptedString("receipts.notes"))
    # Phone uploads only: the phone's own ID for the receipt, so a retried upload never makes a
    # second copy (sync contract §6.3). ``deduction_kind`` is the phone's tag for a tax receipt.
    client_id: Mapped[str | None] = mapped_column(String(36), unique=True)
    deduction_kind: Mapped[str | None] = mapped_column(String(16))
    # Which phone uploaded it, so only that phone is told "duplicate" for its own ``client_id``.
    device_id: Mapped[int | None] = mapped_column(ForeignKey("devices.id", ondelete="SET NULL"))

    @property
    def has_image(self) -> bool:
        return self.image_path is not None
