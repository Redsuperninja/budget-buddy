"""Database tables. Importing this package registers every model on ``Base.metadata``."""

from app.models.base import Base
from app.models.devices import Device, PairingNonce, PairingSession, RemoteComputer, SeenNonce
from app.models.enums import (
    AccountKind,
    CategoryGroup,
    CategorySource,
    DeductionKind,
    DonationKind,
    RetirementType,
    TransactionKind,
    TransactionSource,
)
from app.models.imports import ImportBatch
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
from app.models.tax import (
    Deduction,
    Dividend,
    Donation,
    Position,
    PriceFeed,
    StockLot,
    StockPrice,
    StockSale,
    StockSaleOrder,
)

__all__ = [
    "Account",
    "AccountKind",
    "Base",
    "BudgetPlan",
    "Category",
    "CategoryGroup",
    "CategorySource",
    "CategoryRule",
    "CsvImportMapping",
    "Deduction",
    "DeductionKind",
    "Device",
    "Dividend",
    "Donation",
    "ImportBatch",
    "DonationKind",
    "PairingNonce",
    "PairingSession",
    "Paycheck",
    "Receipt",
    "RemoteComputer",
    "RetirementType",
    "SeenNonce",
    "StockLot",
    "StockPrice",
    "Position",
    "PriceFeed",
    "StockSale",
    "StockSaleOrder",
    "Transaction",
    "TransactionKind",
    "TransactionSource",
]
