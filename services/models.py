"""
Domain models and enums for the Stripe service layer.

Using str-based enums means enum members can be passed directly to the
Stripe SDK (which expects plain strings) without calling .value.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class RecurringInterval(str, Enum):
    """Billing intervals supported by Stripe."""
    DAY   = 'day'
    WEEK  = 'week'
    MONTH = 'month'
    YEAR  = 'year'


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


@dataclass
class BillingAddress:
    """Structured billing / shipping address passed to Stripe.

    All fields are optional so callers can supply only what they have.
    """
    name: str | None = field(default=None)
    line1: str | None = field(default=None)
    line2: str | None = field(default=None)
    city: str | None = field(default=None)
    state: str | None = field(default=None)
    postal_code: str | None = field(default=None)
    country: str | None = field(default=None)

    def to_dict(self) -> dict:
        """Return a plain dict suitable for the Stripe API."""
        return {
            'name': self.name,
            'line1': self.line1,
            'line2': self.line2,
            'city': self.city,
            'state': self.state,
            'postal_code': self.postal_code,
            'country': self.country,
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'BillingAddress':
        """Build a BillingAddress from a raw request dict."""
        if not data:
            return cls()
        return cls(
            name=data.get('name'),
            line1=data.get('line1'),
            line2=data.get('line2'),
            city=data.get('city'),
            state=data.get('state'),
            postal_code=data.get('postal_code'),
            country=data.get('country'),
        )
