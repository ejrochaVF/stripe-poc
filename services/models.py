"""
Domain models and enums for the Stripe service layer.

Using str-based enums means enum members can be passed directly to the
Stripe SDK (which expects plain strings) without calling .value.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class RecurringInterval(str, Enum):
    """Billing intervals supported by Stripe."""
    DAY   = 'day'
    WEEK  = 'week'
    MONTH = 'month'
    YEAR  = 'year'

    def __str__(self) -> str:
        return self.value


class Currency(str, Enum):
    """Common currencies supported by Stripe.

    This list covers the most frequently used currencies.
    Stripe supports ~135 currencies in total; add more as needed.
    Zero-decimal currencies (e.g. JPY, KRW) are included and handled
    automatically by StripeService.to_minor_unit.
    """
    # Major currencies
    USD = 'usd'
    EUR = 'eur'
    GBP = 'gbp'
    CAD = 'cad'
    AUD = 'aud'
    NZD = 'nzd'
    CHF = 'chf'
    SEK = 'sek'
    NOK = 'nok'
    DKK = 'dkk'
    SGD = 'sgd'
    HKD = 'hkd'
    MXN = 'mxn'
    BRL = 'brl'
    INR = 'inr'
    PLN = 'pln'
    CZK = 'czk'
    HUF = 'huf'
    ILS = 'ils'
    AED = 'aed'
    SAR = 'sar'
    # Zero-decimal currencies
    JPY = 'jpy'
    KRW = 'krw'
    VND = 'vnd'
    CLP = 'clp'

    def __str__(self) -> str:
        return self.value

