from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
import math

from .transitions import ContractError


@dataclass(frozen=True)
class MarketSnapshot:
    symbol: str
    role: str
    price: float
    price_date: str
    retrieved_at: str
    currency: str
    provider: str
    semantics: str

    def __post_init__(self) -> None:
        try:
            if isinstance(self.price, bool) or not math.isfinite(float(self.price)) or float(self.price) <= 0:
                raise ValueError("invalid price")
            if date.fromisoformat(self.price_date).isoformat() != self.price_date:
                raise ValueError("noncanonical date")
        except (TypeError, ValueError, OverflowError) as error:
            raise ContractError("snapshot requires a positive finite price and YYYY-MM-DD date") from error
        try:
            # Python 3.9 needs an explicit UTC offset.
            stamp = self.retrieved_at
            if isinstance(stamp, str) and stamp.endswith('Z'):
                stamp = stamp[:-1] + '+00:00'
            retrieved = datetime.fromisoformat(stamp)
            if retrieved.utcoffset() is None:
                raise ValueError('timezone required')
        except (TypeError, ValueError, OverflowError) as error:
            raise ContractError('snapshot requires a parseable timezone-aware retrieved_at') from error
        if any(not isinstance(value, str) or not value.strip()
               for value in (self.symbol, self.currency, self.provider, self.semantics)):
            raise ContractError("snapshot requires explicit symbol/currency/provider/semantics")
