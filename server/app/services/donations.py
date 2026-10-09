"""Charitable donations: list, add, change, remove, and the yearly summary (roadmap #11).

The paperwork each gift needs is in ``donation_proof``. A donation counts in the calendar year of
its date. These are estimates, not tax advice.
"""

import datetime as dt
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import tax_data
from app.errors import ApiError, not_found
from app.models import Donation, DonationKind, Receipt
from app.schemas.donations import (
    DonationCreate,
    DonationOut,
    DonationPage,
    DonationProof,
    DonationSummary,
    DonationUpdate,
    ProofThresholds,
)
from app.services.donation_payments import (
    check_payment,
    commit,
    file_new_link,
    part_gift_proof,
    payment_amounts,
)
from app.services.donation_proof import donation_proof, year_proof

DISCLAIMER = (
    "This is an estimate to help you keep the right records. It isn't tax advice. Some gifts "
    "have extra rules, such as cars, boats, stock, or gifts where you got something back. Check "
    "IRS Publication 526 or ask a tax professional before you file. These totals are what you "
    "gave, not what you can deduct. How much counts depends on whether you itemize and on your "
    "income."
)


@dataclass(frozen=True)
class DonationFilters:
    tax_year: int | None = None
    kind: DonationKind | None = None
    limit: int = 100
    offset: int = 0


def _year_range(year: int) -> tuple[dt.date, dt.date]:
    return dt.date(year, 1, 1), dt.date(year, 12, 31)


def _out(donation: Donation) -> DonationOut:
    columns = {c.key: getattr(donation, c.key) for c in Donation.__table__.columns}
    return DonationOut.model_validate({**columns, "tax_year": donation.date.year})


def get_donation(session: Session, donation_id: int) -> Donation:
    donation = session.get(Donation, donation_id)
    if donation is None:
        raise not_found("donation")
    return donation


def _check_references(session: Session, data: dict) -> None:
    if data.get("receipt_id") is not None and session.get(Receipt, data["receipt_id"]) is None:
        raise not_found("receipt")


def list_donations(session: Session, filters: DonationFilters) -> DonationPage:
    """Newest first (by date, then most recently added)."""
    query = select(Donation)
    if filters.tax_year is not None:
        start, end = _year_range(filters.tax_year)
        query = query.where(Donation.date >= start, Donation.date <= end)
    if filters.kind is not None:
        query = query.where(Donation.kind == filters.kind)
    total = session.scalar(select(func.count()).select_from(query.subquery()))
    items = session.scalars(
        query.order_by(Donation.date.desc(), Donation.id.desc())
        .limit(filters.limit)
        .offset(filters.offset)
    ).all()
    return DonationPage(
        items=[_out(d) for d in items], total=total, limit=filters.limit, offset=filters.offset
    )


def donation_out(session: Session, donation_id: int) -> DonationOut:
    return _out(get_donation(session, donation_id))


def create_donation(session: Session, data: DonationCreate) -> DonationOut:
    values = data.model_dump(exclude={"amount"})
    _check_references(session, values)
    check_payment(session, values["transaction_id"], values["kind"], values["amount_cents"])
    file_new_link(session, values["transaction_id"], None)
    donation = Donation(**values)
    session.add(donation)
    commit(session)
    return _out(donation)


def update_donation(session: Session, donation_id: int, data: DonationUpdate) -> DonationOut:
    donation = get_donation(session, donation_id)
    changes = data.changes()
    changes.pop("amount", None)
    _check_references(session, changes)
    check_payment(
        session,
        changes.get("transaction_id", donation.transaction_id),
        changes.get("kind", donation.kind),
        changes.get("amount_cents", donation.amount_cents),
        donation.id,
    )
    if "transaction_id" in changes:
        file_new_link(session, changes["transaction_id"], donation.transaction_id)
    for field, value in changes.items():
        setattr(donation, field, value)
    commit(session)
    return _out(donation)


def delete_donation(session: Session, donation_id: int) -> None:
    session.delete(get_donation(session, donation_id))
    session.commit()


def summary(session: Session, year: int) -> DonationSummary:
    try:
        data = tax_data.load_tax_year(year)
    except tax_data.UnsupportedTaxYearError as exc:
        years = ", ".join(str(y) for y in exc.supported) or "none yet"
        raise ApiError(
            404,
            "no_tax_data",
            f"Budget Buddy doesn't have tax rules for {year} yet. Years it has: {years}.",
        ) from None
    rules = data.charitable
    start, end = _year_range(year)
    donations = session.scalars(
        select(Donation)
        .where(Donation.date >= start, Donation.date <= end)
        .order_by(Donation.date, Donation.id)
    ).all()
    cash = sum(d.amount_cents for d in donations if d.kind == DonationKind.CASH)
    goods_amounts = [d.amount_cents for d in donations if d.kind == DonationKind.GOODS]
    goods = sum(goods_amounts)
    payments = payment_amounts(session, donations)
    return DonationSummary(
        tax_year=year,
        is_estimate=True,
        disclaimer=DISCLAIMER,
        donation_count=len(donations),
        cash_total_cents=cash,
        goods_total_cents=goods,
        total_cents=cash + goods,
        year_proof_needed=year_proof(goods_amounts, rules),
        donations=[
            DonationProof(
                donation_id=d.id,
                date=d.date,
                organization=d.organization,
                kind=d.kind,
                amount_cents=d.amount_cents,
                has_receipt=d.receipt_id is not None,
                proof_needed=donation_proof(d.kind, d.amount_cents, rules)
                + part_gift_proof(d.amount_cents, payments.get(d.transaction_id)),
            )
            for d in donations
        ],
        thresholds=ProofThresholds(
            written_acknowledgment_cents=rules.written_acknowledgment_threshold_cents,
            form_8283_noncash_cents=rules.form_8283_noncash_threshold_cents,
            qualified_appraisal_cents=rules.qualified_appraisal_threshold_cents,
        ),
        tax_data_last_reviewed=data.last_reviewed,
    )
