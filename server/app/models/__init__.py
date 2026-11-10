"""Database tables. Importing this package registers every model on ``Base.metadata``."""

from app.models.base import Base
from app.models.devices import Device, PairingNonce, PairingSession, RemoteComputer, SeenNonce
from app.models.enums import (
    AccountKind,
    CategoryGroup,
    CategorySource,
    DeductionKind,
    DonationKind,
    PaycheckLineKind,
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
    PaycheckLine,
    Receipt,
    Transaction,
)
from app.models.setup import SetupProgress
from app.models.splits import TransactionSplit
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
from app.models.tax_preferences import TaxPreferences
from app.models.trades import BankTrade, SecuritySymbol

__all__ = [
    "SetupProgress",
    "TaxPreferences",
    "Account",
    "AccountKind",
    "Base",
    "BankTrade",
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
    "PaycheckLineKind",
    "PairingNonce",
    "PairingSession",
    "Paycheck",
    "PaycheckLine",
    "TransactionSplit",
    "Receipt",
    "RemoteComputer",
    "RetirementType",
    "SecuritySymbol",
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
