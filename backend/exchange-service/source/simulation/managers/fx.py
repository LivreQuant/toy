from dataclasses import dataclass
from typing import Dict, Optional, List
from datetime import datetime
from threading import RLock
import logging
from decimal import Decimal
from source.simulation.core.models.models import FXRate


class FXManager:
    def __init__(self, tracking: bool = False):
        self._lock = RLock()
        self.fx: Dict[str, FXRate] = {}  # key will be "FROM/TO"
        self.previous_fx: Dict[str, FXRate] = {}  # Store previous rates
        self.logger = logging.getLogger(self.__class__.__name__)

    def _get_rate_key(self, from_currency: str, to_currency: str) -> str:
        """Get the key for storing/retrieving FX rates"""
        return f"{from_currency}/{to_currency}"

    def _add_derived_rates(self, fx: List[FXRate]) -> List[FXRate]:
        """Add inverse rates and same-currency rates for all currencies involved"""
        currencies = set()
        new_rates = fx.copy()

        # First collect all unique currencies - FIX: Use attribute access, not dictionary access
        for rate in fx:
            currencies.add(rate.from_currency)  # Fixed: was rate['from_currency']
            currencies.add(rate.to_currency)    # Fixed: was rate['to_currency']

        # Create a set of existing rate keys
        existing_keys = {self._get_rate_key(rate.from_currency, rate.to_currency)
                         for rate in new_rates}

        # Add inverse rates if they don't exist
        for rate in fx:
            inverse_key = self._get_rate_key(rate.to_currency, rate.from_currency)
            if inverse_key not in existing_keys:
                inverse_rate = FXRate(
                    from_currency=rate.to_currency,
                    to_currency=rate.from_currency,
                    rate=Decimal('1') / Decimal(str(rate.rate))
                )
                new_rates.append(inverse_rate)
                existing_keys.add(inverse_key)

        # Add same-currency rates
        for currency in currencies:
            same_curr_key = self._get_rate_key(currency, currency)
            if same_curr_key not in existing_keys:
                same_curr_rate = FXRate(
                    from_currency=currency,
                    to_currency=currency,
                    rate=Decimal('1')
                )
                new_rates.append(same_curr_rate)
                existing_keys.add(same_curr_key)

        return new_rates

    def save_current_as_previous(self) -> None:
        """Save current rates as previous rates before updating with new data"""
        with self._lock:
            self.previous_fx = {
                key: FXRate(
                    from_currency=rate.from_currency,
                    to_currency=rate.to_currency,
                    rate=Decimal(str(rate.rate))
                )
                for key, rate in self.fx.items()
            }

    def submit_last_snap_rates(self, last_snap_rates: List[FXRate], timestamp: datetime) -> None:
        """Submit last snapshot FX rates"""
        try:
            complete_rates = self._add_derived_rates(last_snap_rates)

            with self._lock:
                self.save_current_as_previous()  # Save current before updating

                for fx in complete_rates:
                    key = self._get_rate_key(fx.from_currency, fx.to_currency)
                    self.fx[key] = fx

            self.logger.debug(f"✅ Submitted {len(complete_rates)} FX rates (including derived rates)")

        except Exception as e:
            self.logger.error(f"❌ Error submitting FX rates: {e}")
            raise

    def update_rates(self, rates: List[FXRate]) -> None:
        """Update FX rates"""
        try:
            complete_rates = self._add_derived_rates(rates)

            with self._lock:
                self.save_current_as_previous()

                for fx in complete_rates:
                    key = self._get_rate_key(fx.from_currency, fx.to_currency)
                    self.fx[key] = fx

            self.logger.debug(f"✅ Updated {len(complete_rates)} FX rates (including derived rates)")

        except Exception as e:
            self.logger.error(f"❌ Error updating FX rates: {e}")
            raise

    def get_rate(self, from_currency: str, to_currency: str, current: bool = True) -> Optional[Decimal]:
        """Get FX rate for a currency pair, either current or previous based on flag"""
        with self._lock:
            rates_dict = self.fx if current else self.previous_fx
            rate = rates_dict.get(self._get_rate_key(from_currency, to_currency))
            return Decimal(str(rate.rate)) if rate else None

    def get_all_rates(self, current: bool = True) -> Dict[str, FXRate]:
        """Get all FX rates, either current or previous based on flag"""
        with self._lock:
            rates_dict = self.fx if current else self.previous_fx
            return rates_dict.copy()

    def convert_amount(self, amount: Decimal, from_currency: str, to_currency: str, current: bool = True) -> Optional[Decimal]:
        """Convert amount between currencies using FX rates, either current or previous based on flag"""
        if from_currency == to_currency:
            return amount

        with self._lock:
            rates_dict = self.fx if current else self.previous_fx

            # Try direct conversion
            direct_key = self._get_rate_key(from_currency, to_currency)
            if direct_key in rates_dict:
                rate = Decimal(str(rates_dict[direct_key].rate))
                return amount * rate

            # Try inverse conversion
            inverse_key = self._get_rate_key(to_currency, from_currency)
            if inverse_key in rates_dict:
                rate = Decimal(str(rates_dict[inverse_key].rate))
                return amount / rate

            # Try USD as intermediate
            usd_from_key = self._get_rate_key(from_currency, "USD")
            usd_to_key = self._get_rate_key("USD", to_currency)

            if usd_from_key in rates_dict and usd_to_key in rates_dict:
                from_rate = Decimal(str(rates_dict[usd_from_key].rate))
                to_rate = Decimal(str(rates_dict[usd_to_key].rate))

                usd_amount = amount * from_rate
                return usd_amount * to_rate

        return None

    def get_fx_summary(self) -> Dict:
        """Get a summary of current FX rates for debugging"""
        with self._lock:
            return {
                'total_rates': len(self.fx),
                'currencies': sorted(list(set(
                    [rate.from_currency for rate in self.fx.values()] +
                    [rate.to_currency for rate in self.fx.values()]
                ))),
                'sample_rates': {k: f"{v.from_currency}/{v.to_currency}={v.rate}"
                               for k, v in list(self.fx.items())[:5]}
            }