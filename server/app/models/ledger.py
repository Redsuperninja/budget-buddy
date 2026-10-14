"""Accounts, categories, transactions, paychecks, and receipts. Amounts are integer cents."""

import datetime as dt

from sqlalchemy import CheckConstraint, Date, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.crypto.fields import EncryptedString
from app.models.base import Base, TimestampMixin, str_enum
from app.models.enums import AccountKind, CategoryGroup, TransactionKind, TransactionSource
from app.transfer_types import classify


class Account(TimestampMixin, Base):
    __tablename__ = "accounts"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    kind: Mapped[AccountKind] = mapped_column(str_enum(AccountKind, "account_kind"))
    institution: Mapped[str | None] = mapped_column(String(100))
    last4: Mapped[str | None] = mapped_column(EncryptedString("accounts.last4"))
    notes: Mapped[str | None] = mapped_column(EncryptedString("accounts.notes"))
    # Retirement accounts only: Roth IRA, traditional IRA, 401(k)... (enums.RetirementType).
    retirement_type: Mapped[str | None] = mapped_column(String(16))


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
    # Made by Budget Buddy from the categories you kept picking (services/category_learning.py).
    learned: Mapped[bool] = mapped_column(default=False, server_default="0")


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
    # an overlapping statement again doesn't add the same rows twice.
    # See services/imports/csv_import.py.
    import_fingerprint: Mapped[str | None] = mapped_column(String(64), unique=True, index=True)
    # How the category was set: "rule" (auto-sort) or "you" (picked by hand); None for older rows
    # and categories set by Budget Buddy itself (transfers). See enums.CategorySource.
    category_source: Mapped[str | None] = mapped_column(String(8))
    # The rule that sorted it. No foreign key (adding one would mean rebuilding this table, which
    # other tables point at); deleting a rule clears it in services/category_rules.py.
    sorted_by_rule_id: Mapped[int | None] = mapped_column(Integer, index=True)
    # The file import that added it (``imports``), so the import can be undone. No foreign key,
    # like sorted_by_rule_id (migration 0022 only adds columns).
    import_id: Mapped[int | None] = mapped_column(Integer, index=True)
    # Set when you undo a transfer link, so automatic matching never links it again.
    auto_transfer_off: Mapped[bool] = mapped_column(default=False, server_default="0")
    # The category (and how it was set) from before it was linked as a transfer, put back when the
    # link is undone. No foreign keys, like sorted_by_rule_id (migration 0016 only adds columns).
    pre_transfer_category_id: Mapped[int | None] = mapped_column(Integer)
    pre_transfer_category_source: Mapped[str | None] = mapped_column(String(8))
    pre_transfer_rule_id: Mapped[int | None] = mapped_column(Integer)
    account = relationship("Account", viewonly=True, lazy="selectin")
    transfer_partner = relationship(
        "Transaction",
        primaryjoin="foreign(Transaction.transfer_pair_id) == remote(Transaction.id)",
        uselist=False,
        viewonly=True,
        lazy="selectin",
    )
    # The charitable gift this payment is, if it was sorted into charity (Donation.transaction_id).
    donation = relationship(
        "Donation",
        primaryjoin="Transaction.id == foreign(Donation.transaction_id)",
        uselist=False,
        viewonly=True,
        lazy="selectin",
    )

    @property
    def donation_id(self) -> int | None:
        return self.donation.id if self.donation is not None else None

    @property
    def transfer_type(self) -> str | None:
        """A linked transfer's kind (app/transfer_types.py), the same on both sides."""
        partner = self.transfer_partner
        if self.kind != TransactionKind.TRANSFER or partner is None:
            return None
        out, into = (self, partner) if self.amount_cents < 0 else (partner, self)
        return classify(out.account.kind, into.account.kind).value


class CsvImportMapping(TimestampMixin, Base):
    """The column mapping saved for an account, so its next CSV import is one click."""

    __tablename__ = "csv_import_mappings"

    account_id: Mapped[int] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"), primary_key=True
    )
    # JSON, see app.schemas.imports.csv_import.CsvMapping
    mapping: Mapped[str] = mapped_column(Text)


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
