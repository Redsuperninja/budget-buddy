"""Other deductions (roadmap #13): add, edit, list by tax year, and remove.

Each kind also says where it usually goes on a US federal return, in plain English, because the
kinds don't add up to one number: some count only if you itemize (and have limits, such as the
medical-expense floor or the SALT cap), some lower your income even if you don't, and some are tax
credits rather than deductions. These are hints for getting records together, not tax advice.
"""

from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.errors import ApiError, not_found
from app.models import Deduction, DeductionKind, Receipt
from app.schemas.deductions import DeductionCreate, DeductionUpdate

Where = Literal["itemized", "adjustment", "credit", "other"]

LABELS = {
    DeductionKind.MEDICAL: "Medical",
    DeductionKind.EDUCATION: "Education",
    DeductionKind.STUDENT_LOAN_INTEREST: "Student loan interest",
    DeductionKind.HOME_OFFICE: "Home office",
    DeductionKind.MORTGAGE_INTEREST: "Mortgage interest",
    DeductionKind.PROPERTY_TAX: "Property tax",
    DeductionKind.STATE_LOCAL_TAX: "State and local taxes",
    DeductionKind.HSA: "Health savings account",
    DeductionKind.IRA: "IRA contributions",
    DeductionKind.CHILDCARE: "Childcare",
    DeductionKind.OTHER: "Other",
}

WHERE: dict[DeductionKind, Where] = {
    DeductionKind.MEDICAL: "itemized",
    DeductionKind.MORTGAGE_INTEREST: "itemized",
    DeductionKind.PROPERTY_TAX: "itemized",
    DeductionKind.STATE_LOCAL_TAX: "itemized",
    DeductionKind.STUDENT_LOAN_INTEREST: "adjustment",
    DeductionKind.HSA: "adjustment",
    DeductionKind.IRA: "adjustment",
    DeductionKind.EDUCATION: "credit",
    DeductionKind.CHILDCARE: "credit",
    DeductionKind.HOME_OFFICE: "other",
    DeductionKind.OTHER: "other",
}

WHERE_TEXT: dict[Where, str] = {
    "itemized": "Counts only if you itemize, and limits apply (Schedule A).",
    "adjustment": "Can lower your income even if you don't itemize, within limits.",
    "credit": "May qualify for a tax credit rather than a deduction.",
    "other": "Usually only for self-employed people (a home office used only for work).",
}


# Kinds whose rules don't fit their group's general text.
HINTS: dict[DeductionKind, str] = {
    DeductionKind.HSA: (
        "Only money you put in yourself, not through your paycheck (that's already left out of "
        "your taxable pay). The yearly limit includes your employer's share."
    ),
    DeductionKind.IRA: (
        "Traditional IRA only, not Roth. It may be limited if you have a retirement plan at work."
    ),
    DeductionKind.OTHER: "Depends on what it is. Check the IRS instructions or a tax professional.",
}


def hint(kind: DeductionKind) -> str:
    """Where this kind usually goes on a federal return, in plain English."""
    return HINTS.get(kind) or WHERE_TEXT[WHERE[kind]]


def label(kind: DeductionKind) -> str:
    return LABELS.get(kind, kind.value.replace("_", " ").capitalize())


def get_deduction(session: Session, deduction_id: int) -> Deduction:
    deduction = session.get(Deduction, deduction_id)
    if deduction is None:
        raise not_found("deduction")
    return deduction


def _check_receipt(session: Session, receipt_id: int | None) -> None:
    if receipt_id is not None and session.get(Receipt, receipt_id) is None:
        raise not_found("receipt")


def list_deductions(session: Session, tax_year: int) -> list[Deduction]:
    """One tax year's deductions, by date (undated last), then as added."""
    return list(
        session.scalars(
            select(Deduction)
            .where(Deduction.tax_year == tax_year)
            .order_by(Deduction.date.is_(None), Deduction.date, Deduction.id)
        )
    )


def create_deduction(session: Session, data: DeductionCreate) -> Deduction:
    values = data.model_dump(exclude={"amount"})
    _check_receipt(session, values["receipt_id"])
    deduction = Deduction(**values)
    session.add(deduction)
    session.commit()
    return deduction


def update_deduction(session: Session, deduction_id: int, data: DeductionUpdate) -> Deduction:
    deduction = get_deduction(session, deduction_id)
    changes = data.changes()
    changes.pop("amount", None)
    _check_receipt(session, changes.get("receipt_id"))
    year = changes.get("tax_year", deduction.tax_year)
    date = changes.get("date", deduction.date)
    if date is not None and date.year != year:
        raise ApiError(422, "validation_error", "The date has to be in the tax year you picked.")
    for field, value in changes.items():
        setattr(deduction, field, value)
    session.commit()
    return deduction


def delete_deduction(session: Session, deduction_id: int) -> None:
    session.delete(get_deduction(session, deduction_id))
    session.commit()
