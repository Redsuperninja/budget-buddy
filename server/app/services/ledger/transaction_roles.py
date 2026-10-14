"""What a transaction is used as, beyond its kind and category: a paycheck's deposit, a donation,
a stock trade, a trade or dividend found in a bank file, or the deposit sweep next to one. Each
role is a link from another table; this is the one place that knows those links, so a new role
is added here once instead of in every query that must leave it out.

Each role is a select of transaction ids. ``none_of`` turns roles into conditions, one NOT IN
each, since SQLite can't nest one UNION inside another.

Only a dividend or bank trade that isn't dismissed gets a sweep, and dismissing one frees its
sweep, so every linked sweep belongs to one that's shown.
"""

from sqlalchemy import select

from app.models import (
    Account,
    BankTrade,
    Dividend,
    Donation,
    Paycheck,
    StockLot,
    StockSaleOrder,
    Transaction,
)
from app.services.ledger.accounts import TAX_FREE_KINDS


def none_of(*roles) -> list:
    """Conditions: the transaction has none of these roles."""
    return [Transaction.id.not_in(role) for role in roles]


def paycheck_deposits():
    return select(Paycheck.deposit_transaction_id).where(
        Paycheck.deposit_transaction_id.is_not(None)
    )


def donations():
    return select(Donation.transaction_id).where(Donation.transaction_id.is_not(None))


def stock_trades():
    """Recorded as a stock purchase or sale: cash turning into shares (or back)."""
    return (
        select(StockLot.transaction_id)
        .where(StockLot.transaction_id.is_not(None))
        .union(
            select(StockSaleOrder.transaction_id).where(StockSaleOrder.transaction_id.is_not(None))
        )
    )


def bank_trades(*, include_dismissed: bool = False):
    """Found in a bank file as a trade. Dismissed ones are remembered so they aren't found again."""
    query = select(BankTrade.transaction_id)
    return query if include_dismissed else query.where(BankTrade.dismissed.is_(False))


def bank_trade_sweeps():
    return select(BankTrade.sweep_transaction_id).where(BankTrade.sweep_transaction_id.is_not(None))


def dividends(*, include_dismissed: bool = False):
    query = select(Dividend.transaction_id)
    return query if include_dismissed else query.where(Dividend.dismissed.is_(False))


def dividend_sweeps():
    return select(Dividend.sweep_transaction_id).where(Dividend.sweep_transaction_id.is_not(None))


def cash_inside_account() -> list:
    """Roles of cash turning into shares or back inside an account: never spending, income or a
    transfer."""
    return [stock_trades(), bank_trades(), bank_trade_sweeps()]


def dividends_kept_inside() -> list:
    """Roles of a dividend paid inside a retirement account or HSA, and its sweep. That cash stays
    in the account, so it isn't take-home income or new saving."""
    inside = (
        select(Dividend)
        .join(Transaction, Transaction.id == Dividend.transaction_id)
        .join(Account, Account.id == Transaction.account_id)
        .where(Dividend.dismissed.is_(False), Account.kind.in_(TAX_FREE_KINDS))
    )
    return [
        inside.with_only_columns(Dividend.transaction_id),
        inside.with_only_columns(Dividend.sweep_transaction_id).where(
            Dividend.sweep_transaction_id.is_not(None)
        ),
    ]
