"""The paperwork each charitable gift needs, and what depends on the whole year (roadmap #11).

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

These are estimates, not tax advice.
"""

from app.models import DonationKind
from app.money import cents_to_display
from app.schemas.tax.donations import ProofItem
from app.tax_data import Charitable


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
