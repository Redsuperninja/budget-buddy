from enum import StrEnum


class AccountKind(StrEnum):
    CHECKING = "checking"
    SAVINGS = "savings"
    BROKERAGE = "brokerage"


class CategoryGroup(StrEnum):
    NEEDS = "needs"
    WANTS = "wants"
    SAVINGS = "savings"
    INCOME = "income"


class TransactionSource(StrEnum):
    CSV = "csv"
    MANUAL = "manual"
    RECEIPT = "receipt"


class DonationKind(StrEnum):
    CASH = "cash"
    GOODS = "goods"


class DeductionKind(StrEnum):
    MEDICAL = "medical"
    EDUCATION = "education"
    STUDENT_LOAN_INTEREST = "student_loan_interest"
    HOME_OFFICE = "home_office"
    MORTGAGE_INTEREST = "mortgage_interest"
    PROPERTY_TAX = "property_tax"
    STATE_LOCAL_TAX = "state_local_tax"
    HSA = "hsa"
    IRA = "ira"
    CHILDCARE = "childcare"
    OTHER = "other"
