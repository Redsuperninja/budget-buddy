"""What kind of transfer a linked pair is, from the two accounts' types: a credit card payment,
money into savings, investments, retirement or an HSA, or money taken back out of them.

It's worked out (never stored), so changing an account's type relabels its transfers. It's a label
only: whether money counts as saved is decided in ``services/ledger/savings_transfers.py``.
"""

from enum import StrEnum

from app.models.enums import AccountKind


class TransferType(StrEnum):
    CARD_PAYMENT = "card_payment"
    LOAN_PAYMENT = "loan_payment"
    TO_SAVINGS = "to_savings"
    TO_INVESTMENTS = "to_investments"
    TO_RETIREMENT = "to_retirement"
    TO_HSA = "to_hsa"
    FROM_SAVINGS = "from_savings"
    FROM_INVESTMENTS = "from_investments"
    FROM_RETIREMENT = "from_retirement"
    FROM_HSA = "from_hsa"
    BETWEEN_ACCOUNTS = "between_accounts"


_INTO = {
    AccountKind.CREDIT_CARD: TransferType.CARD_PAYMENT,
    AccountKind.LOAN: TransferType.LOAN_PAYMENT,
    AccountKind.SAVINGS: TransferType.TO_SAVINGS,
    AccountKind.BROKERAGE: TransferType.TO_INVESTMENTS,
    AccountKind.RETIREMENT: TransferType.TO_RETIREMENT,
    AccountKind.HSA: TransferType.TO_HSA,
}
_OUT_OF = {
    AccountKind.SAVINGS: TransferType.FROM_SAVINGS,
    AccountKind.BROKERAGE: TransferType.FROM_INVESTMENTS,
    AccountKind.RETIREMENT: TransferType.FROM_RETIREMENT,
    AccountKind.HSA: TransferType.FROM_HSA,
}


# Money doesn't leave these for your other accounts (a card or loan payment is money into them).
CANT_SEND = frozenset({AccountKind.CREDIT_CARD, AccountKind.LOAN})


def classify(from_kind: AccountKind, to_kind: AccountKind) -> TransferType:
    """Money moved out of a ``from_kind`` account into a ``to_kind`` account. Where it went decides
    first (paying a card from savings is still a card payment)."""
    return _INTO.get(to_kind) or _OUT_OF.get(from_kind) or TransferType.BETWEEN_ACCOUNTS
