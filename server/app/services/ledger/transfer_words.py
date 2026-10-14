"""Words that make a bank line look like money moving between your own accounts, a card payment,
or not a transfer at all. Shared by transfer matching (``transfer_matching``), card payments
(``card_payments``) and card-file signs (``imports/card_signs``)."""

import re

WORDS = r"(?<![a-z])(?:{})(?![a-z])"
TRANSFER_WORDS = re.compile(
    WORDS.format(
        "transfer|xfer|trnsfr|tfr|payment|pymt|pmt|autopay|auto pay|thank you|online banking|ach|"
        "contribution|contrib|to savings|from savings|to checking|from checking|to sav|from chk|"
        "internal|move money|zelle to self"
    ),
    re.I,
)
CARD_PAYMENT_WORDS = re.compile(
    WORDS.format("payment|pymt|pmt|autopay|auto pay|thank you|online banking|ach"), re.I
)
NOT_TRANSFER_WORDS = re.compile(
    WORDS.format(
        "div|dividend|dividends|interest|int pd|reinvest|reinvestment|employer|match|payroll|"
        "direct dep|dir dep|salary|refund|return|credit adj|cashback|cash back|reward|rewards"
    ),
    re.I,
)
# A payment out of your bank account that names a credit card (with ``CARD_PAYMENT_WORDS``). Never
# the bare word "card": debit-card purchases say "card" and often "payment" too.
CARD_WORDS = re.compile(
    WORDS.format(
        "credit card|credit crd|cr card|cardmember|card services|card srvc|crd epay|card pmt|"
        "amex|american express|discover|capital one|citi card|citicards|barclaycard|synchrony|"
        "apple card"
    ),
    re.I,
)
# Never a card payment from your bank account: a debit-card purchase, or a loan or savings account
# at a lender that also issues cards ("CAPITAL ONE AUTO LOAN", "DISCOVER BANK SAVINGS").
NOT_CARD_PAYMENT_WORDS = re.compile(
    WORDS.format(
        "debit card|debit crd|check ?card|purchase|authorized|pos|recurring|loans?|ln|personal|"
        "auto finance|mortgage|mtg|student|lease|savings?|bank deposit|discover bank|"
        "capital one 360|synchrony bank|amex natl|american express national|natl bank|"
        "national bank"
    ),
    re.I,
)
# A card payment that bounced or was taken back: it cancels the payment, so it's filed with it.
RETURNED_WORDS = re.compile(WORDS.format("returned|return|reversal|reversed|nsf"), re.I)
# What a card's own payment line says ("PAYMENT THANK YOU", "AUTOPAY PAYMENT"): stricter than
# ``CARD_PAYMENT_WORDS`` (no bare "ACH" or "online banking"), and never a merchant's credit.
CARD_SIDE_WORDS = re.compile(
    WORDS.format("payment|pymt|pmt|autopay|auto pay|thank you|epayment"), re.I
)
NOT_CARD_SIDE_WORDS = re.compile(
    WORDS.format("adj|adjustment|merchant|paypal|purchase|cashback|statement credit"), re.I
)
# Words that say nothing about which card a payment is for, left out when matching a line to the
# names of your card accounts.
GENERIC_WORDS = frozenset(
    "credit crd card cards cr payment pymt pmt autopay auto pay epay epayment ach online banking "
    "thank you web mobile bill transfer to from the and of bank inc co na".split()
)
# Short names a bank line uses for a card company, and the words of its full name.
ISSUER_ALIASES = {"amex": {"american", "express"}, "citi": {"citibank", "citicards"}}

# A fee for a returned payment is a real charge, never filed with the payments.
FEE_WORDS = re.compile(WORDS.format("fee|fees|charge"), re.I)
