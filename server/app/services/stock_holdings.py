"""What you hold now, by account: shares, what they cost, and (with a price you entered) what
they're worth and the gain or loss not yet sold. Estimates for planning, not tax advice.

- Shares held and their cost come from the purchases and the FIFO matching of sales
  (``stock_records.rematch``): a purchase's remaining cost is its cost minus the part its sold
  shares took, using the same half-up rounding as the gains (``stock_gains.share_of``).
- Prices are typed in (one per symbol, with the date), never fetched from the internet. Value =
  shares x price, rounded half up to a cent.
- Retirement and HSA accounts are listed too; their gains aren't taxed when sold (``taxed`` false).
"""

from collections import defaultdict

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Account, StockLot, StockPrice, StockSale
from app.models.tax import SHARES_SCALE
from app.schemas.stock_holdings import AccountHoldingsOut, HoldingOut, HoldingsOut, PriceIn
from app.services import stock_gains as gains
from app.services.stock_records import TAX_FREE_KINDS
from app.shares import micro_to_text

NO_ACCOUNT = "Not in an account"
NOTE = (
    "Values use the prices you typed in, so they're only as current as those. Gains on shares "
    "you still hold aren't taxed until you sell. Selling inside a retirement account or HSA isn't "
    "taxed; money you take out later may be, depending on the account."
)


def value_cents(shares_micro: int, price_cents: int) -> int:
    """Shares (in millionths) times a per-share price, rounded half up to a cent."""
    return gains.share_of(price_cents, shares_micro, SHARES_SCALE)


def set_price(session: Session, data: PriceIn) -> None:
    price = session.get(StockPrice, data.symbol) or StockPrice(symbol=data.symbol)
    price.price_cents = data.price_cents
    price.as_of = data.as_of
    price.source, price.fetched_at = "you", None  # typed in
    session.add(price)
    session.commit()


def holdings(session: Session) -> HoldingsOut:
    lots = session.scalars(select(StockLot)).all()
    sold = dict(
        session.execute(
            select(StockSale.lot_id, func.sum(StockSale.shares_micro)).group_by(StockSale.lot_id)
        ).all()
    )
    held: dict[tuple[int | None, str], list[int]] = defaultdict(lambda: [0, 0])  # shares, cost
    for lot in lots:
        out = sold.get(lot.id, 0)
        left = lot.shares_micro - out
        if left <= 0:
            continue
        cost_left = lot.cost_basis_cents - gains.share_of(
            lot.cost_basis_cents, out, lot.shares_micro
        )
        entry = held[(lot.account_id, lot.symbol)]
        entry[0] += left
        entry[1] += cost_left
    prices = {p.symbol: p for p in session.scalars(select(StockPrice))}
    accounts = {a.id: a for a in session.scalars(select(Account))}
    by_account: dict[int | None, list[HoldingOut]] = defaultdict(list)
    for (account_id, symbol), (shares, cost) in sorted(
        held.items(), key=lambda item: (item[0][0] or 0, item[0][1])
    ):
        price = prices.get(symbol)
        value = value_cents(shares, price.price_cents) if price else None
        by_account[account_id].append(
            HoldingOut(
                symbol=symbol,
                shares_micro=shares,
                shares=micro_to_text(shares),
                cost_basis_cents=cost,
                price_cents=price.price_cents if price else None,
                price_as_of=price.as_of if price else None,
                price_source=price.source if price else None,
                price_fetched_at=price.fetched_at if price else None,
                value_cents=value,
                unrealized_gain_cents=None if value is None else value - cost,
            )
        )
    groups = []
    for account_id, items in by_account.items():
        account = accounts.get(account_id)
        values = [h.value_cents for h in items]
        groups.append(
            AccountHoldingsOut(
                account_id=account_id,
                account_name=account.name if account else NO_ACCOUNT,
                account_kind=account.kind if account else None,
                taxed=not (account and account.kind in TAX_FREE_KINDS),
                holdings=items,
                cost_basis_cents=sum(h.cost_basis_cents for h in items),
                value_cents=None if None in values else sum(values),
            )
        )
    all_values = [g.value_cents for g in groups]
    return HoldingsOut(
        accounts=groups,
        cost_basis_cents=sum(g.cost_basis_cents for g in groups),
        value_cents=None if None in all_values else sum(all_values),
        note=NOTE,
    )
