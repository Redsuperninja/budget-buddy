"""Database tables. Importing this package registers every model on ``Base.metadata``."""

from app.models.base import Base
from app.models.devices import Device, PairingNonce, PairingSession, RemoteComputer, SeenNonce
from app.models.enums import (
    AccountKind,
    CategoryGroup,
    DeductionKind,
    DonationKind,
    TransactionKind,
    TransactionSource,
)
from app.models.ledger import (
    Account,
    BudgetPlan,
    Category,
    CategoryRule,
    CsvImportMapping,
    Paycheck,
    Receipt,
    Transaction,
)
from app.models.tax import Deduction, Donation, StockLot, StockSale, StockSaleOrder

__all__ = [
    "Account",
    "AccountKind",
    "Base",
    "BudgetPlan",
    "Category",
    "CategoryGroup",
    "CategoryRule",
    "CsvImportMapping",
    "Deduction",
    "DeductionKind",
    "Device",
    "Donation",
    "DonationKind",
    "PairingNonce",
    "PairingSession",
    "Paycheck",
    "Receipt",
    "RemoteComputer",
    "SeenNonce",
    "StockLot",
    "StockSale",
    "StockSaleOrder",
    "Transaction",
    "TransactionKind",
    "TransactionSource",
]
