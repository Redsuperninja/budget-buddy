from enum import StrEnum


class AccountKind(StrEnum):
    CHECKING = "checking"
    SAVINGS = "savings"
    BROKERAGE = "brokerage"
    CREDIT_CARD = "credit_card"
    CASH = "cash"
    LOAN = "loan"
    RETIREMENT = "retirement"
    HSA = "hsa"
    OTHER = "other"


class RetirementType(StrEnum):
    """What kind of retirement account it is (only for ``AccountKind.RETIREMENT``)."""

    TRADITIONAL_IRA = "traditional_ira"
    ROTH_IRA = "roth_ira"
    K401 = "401k"
    ROTH_401K = "roth_401k"
    B403 = "403b"
    OTHER = "other"


class CategoryGroup(StrEnum):
    NEEDS = "needs"
    WANTS = "wants"
    SAVINGS = "savings"
    INCOME = "income"
    TRANSFER = "transfer"  # money moving between your own accounts


class TransactionKind(StrEnum):
    NORMAL = "normal"
    TRANSFER = "transfer"  # between your own accounts: not spending or income
    REFUND = "refund"
    ADJUSTMENT = "adjustment"


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


class CategorySource(StrEnum):
    """How a transaction's category was set (plain text in transactions.category_source)."""

    RULE = "rule"  # an auto-sort rule
    YOU = "you"  # picked by hand


class PaycheckLineKind(StrEnum):
    """Extra pay-stub lines that have no column of their own (issue #13)."""

    LOCAL_TAX = "local_tax"
    STATE_DISABILITY = "state_disability"
    PAID_FAMILY_LEAVE = "paid_family_leave"
    HEALTH_FSA = "health_fsa"
    DEPENDENT_CARE_FSA = "dependent_care_fsa"
    EMPLOYER_HSA = "employer_hsa"
    IMPUTED_INCOME = "imputed_income"
    REIMBURSEMENT = "reimbursement"
