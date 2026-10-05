"""Charitable donations and the paperwork each one needs (roadmap #11).

Every dollar threshold comes from that year's tax data file (``app.tax_data``), never from here.
The rules the thresholds plug into (IRS Publication 526, "Records To Keep"):

- Any cash gift: keep a bank or card record, or a written receipt from the charity.
- Any single gift (cash or goods) of the written-acknowledgment threshold *or more* ($250):
  get a written acknowledgment from the charity. Separate gifts are not added together.
- Goods below that threshold: keep a receipt from the charity and your own record of the value.
- Goods for the whole year *more than* the Form 8283 threshold ($500): file Form 8283 if you
  itemize.
- One item (or group of similar items) *more than* the appraisal threshold ($5,000): get a
  qualified appraisal. We can't tell which gifts are "similar", so each goods donation is
  checked on its own. If the year's goods add up to more than the threshold but no single gift
  does, a "check similar items" note asks people to add up similar items themselves.
- From 2026, people who don't itemize can count cash gifts only, up to a limit in the data file.

A donation counts in the calendar year of its date. These are estimates, not tax advice.
"""

import datetime as dt
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import tax_data
from app.errors import ApiError, not_found
from app.models import Donation, DonationKind, Receipt
from app.money import cents_to_display
from app.schemas.donations import (
    DonationCreate,
    DonationOut,
    DonationPage,
    DonationProof,
    DonationSummary,
    DonationUpdate,
    ProofItem,
    ProofThresholds,
)
from app.tax_data import Charitable

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
    donation = Donation(**values)
    session.add(donation)
    session.commit()
    return _out(donation)


def update_donation(session: Session, donation_id: int, data: DonationUpdate) -> DonationOut:
    donation = get_donation(session, donation_id)
    changes = data.changes()
    changes.pop("amount", None)
    _check_references(session, changes)
    for field, value in changes.items():
        setattr(donation, field, value)
    session.commit()
    return _out(donation)


def delete_donation(session: Session, donation_id: int) -> None:
    session.delete(get_donation(session, donation_id))
    session.commit()


# --- Paperwork rules -------------------------------------------------------------------------


def donation_proof(kind: DonationKind, amount_cents: int, rules: Charitable) -> list[ProofItem]:
    """What to keep for one gift. Thresholds come from ``rules`` (that year's tax data)."""
    ack = rules.written_acknowledgment_threshold_cents
    appraisal = rules.qualified_appraisal_threshold_cents
    proof: list[ProofItem] = []
    if amount_cents >= ack:  # "$250 or more"
        what = "how much you gave" if kind == DonationKind.CASH else "a description of the items"
        proof.append(
            ProofItem(
                code="written_acknowledgment",
                message=(
                    f"This gift is {cents_to_display(ack)} or more, so you need a written "
                    f"acknowledgment from the charity before you file. It must show {what} and "
                    "whether you got anything in return, and if so, about what it was worth. A "
                    "bank record alone isn't enough."
                ),
            )
        )
        if kind == DonationKind.GOODS:
            proof.append(
                ProofItem(
                    code="value_note",
                    message=(
                        "Also keep your own note of what the items were worth and how you "
                        "figured it."
                    ),
                )
            )
    elif kind == DonationKind.CASH:
        proof.append(
            ProofItem(
                code="bank_record_or_receipt",
                message=(
                    "Keep a bank or card statement, or a receipt from the charity, that shows "
                    "the charity's name, the date, and the amount."
                ),
            )
        )
    else:
        proof.append(
            ProofItem(
                code="charity_receipt",
                message=(
                    "Keep a receipt from the charity with its name, the date, and a description "
                    "of what you gave, plus your own note of what the items were worth."
                ),
            )
        )
    if kind == DonationKind.GOODS and amount_cents > appraisal:  # "more than $5,000"
        proof.append(
            ProofItem(
                code="qualified_appraisal",
                message=(
                    f"Items worth more than {cents_to_display(appraisal)} usually need a "
                    "qualified appraisal and Section B of Form 8283, signed by the charity. "
                    "Some gifts, like publicly traded stock, don't. If you gave several similar "
                    "items this year, add their values together to check this."
                ),
            )
        )
    return proof


def year_proof(goods_amounts_cents: list[int], rules: Charitable) -> list[ProofItem]:
    """Paperwork and notes that depend on the whole year's gifts rather than on one gift.

    ``goods_amounts_cents`` holds the value of each goods gift made that year.
    """
    form_limit = rules.form_8283_noncash_threshold_cents
    appraisal = rules.qualified_appraisal_threshold_cents
    goods_total = sum(goods_amounts_cents)
    items: list[ProofItem] = []
    if goods_total > form_limit:  # Form 8283 is for "more than $500"
        items.append(
            ProofItem(
                code="form_8283",
                message=(
                    "Your gifts of goods this year add up to more than "
                    f"{cents_to_display(form_limit)}, so if you itemize, you'll likely need to "
                    "file Form 8283 with your return. For each item, keep a note of when and how "
                    "you got it and what you paid for it."
                ),
            )
        )
    # No single gift is over the appraisal line, but similar items given separately may be.
    if goods_total > appraisal and all(a <= appraisal for a in goods_amounts_cents):
        shown = cents_to_display(appraisal)
        items.append(
            ProofItem(
                code="check_similar_items",
                message=(
                    f"Your gifts of goods this year add up to more than {shown}. If several were "
                    "similar items (like clothing or furniture), add their values together. If "
                    f"those add up to more than {shown}, you'll likely need a qualified appraisal "
                    "and Section B of Form 8283."
                ),
            )
        )
    non_itemizer = rules.non_itemizer_deduction_cents
    if non_itemizer is not None:
        single = cents_to_display(non_itemizer.single)
        joint = cents_to_display(non_itemizer.married_filing_jointly)
        items.append(
            ProofItem(
                code="non_itemizer_cash_only",
                message=(
                    f"If you don't itemize, only cash gifts count, up to {single} ({joint} if "
                    "married filing jointly)."
                ),
            )
        )
    return items


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
                proof_needed=donation_proof(d.kind, d.amount_cents, rules),
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
