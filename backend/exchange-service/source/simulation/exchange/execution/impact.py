import math
import time
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Dict, Optional
from threading import RLock

from source.exchange_logging.utils import get_exchange_logger
from source.exchange_logging.context import transaction_scope


@dataclass
class ImpactSnapshot:
    """Represents the impact state at a point in time"""
    start_timestamp: datetime
    end_timestamp: datetime
    current_impact: Decimal  # Current price impact as a percentage
    bin_volume: int  # Volume in current bin
    trade_volume: int  # Volume traded in current bin


class ImpactState:
    def __init__(self, decay_rate: float = 0.1):
        self._lock = RLock()
        self._decay_rate = Decimal(str(decay_rate))
        self._impact_states: Dict[str, ImpactSnapshot] = {}
        self.logger = get_exchange_logger(__name__)

        self.logger.info(f"ImpactState initialized with decay_rate: {decay_rate}")

    def calculate_price_impact(self, symbol: str, currency: str, base_price: Decimal,
                               trade_volume: int, total_volume: int,
                               start_timestamp: datetime, end_timestamp: datetime,
                               trade_id: Optional[str] = None,
                               is_buy: bool = True) -> Decimal:
        """Calculate price impact with comprehensive logging"""

        with transaction_scope("calculate_price_impact", self.logger,
                               symbol=symbol, trade_volume=trade_volume, total_volume=total_volume,
                               trade_id=trade_id, is_buy=is_buy) as txn_id:

            calculation_start_time = time.time()

            with self._lock:
                prev_state = self._impact_states.get(symbol)
                current_impact = Decimal('0')
                permanent_impact = Decimal('0')
                impact_type = "decay"

                self.logger.debug(f"Starting impact calculation for {symbol}")
                self.logger.debug(
                    f"Input params: base_price={base_price}, trade_vol={trade_volume}, total_vol={total_volume}")

                # Step 1: Calculate decay from previous state
                if prev_state:
                    self.logger.debug(f"Found previous impact state: {prev_state.current_impact}")

                    # Calculate time and volume decay factors
                    time_diff = Decimal(str((end_timestamp - prev_state.end_timestamp).total_seconds() / 60))
                    bins_elapsed = max(Decimal('1'), time_diff)
                    volume_ratio = (Decimal(str(total_volume)) / Decimal(str(prev_state.bin_volume))
                                    if prev_state.bin_volume > 0 else Decimal('1'))

                    # Start with previous impact
                    current_impact = prev_state.current_impact

                    # Apply decay based on time and volume
                    decay = -self._decay_rate * bins_elapsed
                    decay_factor = Decimal(str(math.exp(float(decay)))) * volume_ratio
                    current_impact = current_impact * decay_factor

                    self.logger.log_calculation(
                        description="Impact decay calculation",
                        inputs={
                            "previous_impact": str(prev_state.current_impact),
                            "time_diff_minutes": str(time_diff),
                            "bins_elapsed": str(bins_elapsed),
                            "volume_ratio": str(volume_ratio),
                            "decay_rate": str(self._decay_rate)
                        },
                        result=str(current_impact),
                        details={
                            "decay_factor": str(decay_factor),
                            "decay_exponent": str(decay),
                            "symbol": symbol,
                            "trade_id": trade_id or "0",
                            "transaction_id": txn_id
                        }
                    )
                else:
                    self.logger.debug(f"No previous impact state found for {symbol} - starting from zero")

                # Step 2: Handle new trade impact if there's volume
                if trade_volume > 0 and total_volume > 0:
                    trade_vol_dec = Decimal(str(trade_volume))
                    total_vol_dec = Decimal(str(total_volume))
                    volume_ratio = trade_vol_dec / total_vol_dec

                    direction = Decimal('1') if is_buy else Decimal('-1')

                    # Calculate new temporary impact (higher impact)
                    sqrt_ratio = Decimal(str(math.sqrt(float(volume_ratio))))
                    temp_impact = direction * Decimal('0.1') * sqrt_ratio

                    # Calculate new permanent impact (lower impact)
                    perm_impact = direction * Decimal('0.05') * volume_ratio
                    permanent_impact = perm_impact

                    # Add both impacts to current
                    new_trade_impact = temp_impact + permanent_impact
                    current_impact += new_trade_impact

                    # Set impact type based on direction
                    impact_type = "fill_inc" if is_buy else "fill_dec"

                    self.logger.log_calculation(
                        description="New trade impact calculation",
                        inputs={
                            "trade_volume": trade_volume,
                            "total_volume": total_volume,
                            "volume_ratio": str(volume_ratio),
                            "direction": str(direction),
                            "is_buy": is_buy
                        },
                        result=str(new_trade_impact),
                        details={
                            "temporary_impact": str(temp_impact),
                            "permanent_impact": str(permanent_impact),
                            "sqrt_volume_ratio": str(sqrt_ratio),
                            "impact_type": impact_type,
                            "symbol": symbol,
                            "trade_id": trade_id or "0",
                            "transaction_id": txn_id
                        }
                    )

                elif prev_state:
                    # No trade volume - just decay
                    impact_type = "decay"
                    self.logger.debug(f"No trade volume - applying decay only for {symbol}")

                # Step 3: Save new state
                self._impact_states[symbol] = ImpactSnapshot(
                    start_timestamp=start_timestamp,
                    end_timestamp=end_timestamp,
                    current_impact=current_impact,
                    bin_volume=total_volume,
                    trade_volume=trade_volume
                )

                # Calculate final impacted price
                impacted_price = round(base_price * (Decimal('1') + current_impact), 2)
                impact_bps = current_impact * Decimal('10000')  # Convert to basis points

                # Log the final calculation
                self.logger.log_calculation(
                    description="Final price impact result",
                    inputs={
                        "base_price": str(base_price),
                        "current_impact_pct": str(current_impact),
                        "permanent_impact": str(permanent_impact)
                    },
                    result=str(impacted_price),
                    details={
                        "impact_bps": str(impact_bps),
                        "impact_type": impact_type,
                        "symbol": symbol,
                        "trade_id": trade_id or "0",
                        "transaction_id": txn_id
                    }
                )

                # Update impact manager in app state
                from source.orchestration.app_state.state_manager import app_state
                if app_state.impact_manager:
                    app_state.impact_manager.update_impact(
                        symbol=symbol,
                        currency=currency,
                        base_price=base_price,
                        impacted_price=impacted_price,
                        trade_volume=trade_volume,
                        total_volume=total_volume,
                        start_timestamp=start_timestamp,
                        end_timestamp=end_timestamp,
                        trade_id=trade_id,
                        impact_type=impact_type
                    )

                # Performance logging
                calculation_duration = (time.time() - calculation_start_time) * 1000

                self.logger.log_performance(
                    operation=f"price_impact_calculation[{symbol}]",
                    duration_ms=calculation_duration,
                    additional_metrics={
                        "trade_volume": trade_volume,
                        "total_volume": total_volume,
                        "impact_bps": f"{float(impact_bps):.4f}",
                        "impact_type": impact_type,
                        "has_previous_state": prev_state is not None,
                        "trade_id": trade_id or "0"
                    }
                )

                # Log business event for significant impacts
                if abs(impact_bps) > Decimal('1'):  # More than 1 basis point
                    self.logger.log_business_event("SIGNIFICANT_PRICE_IMPACT", {
                        "symbol": symbol,
                        "trade_id": trade_id or "0",
                        "base_price": str(base_price),
                        "impacted_price": str(impacted_price),
                        "impact_bps": str(impact_bps),
                        "trade_volume": trade_volume,
                        "total_volume": total_volume,
                        "impact_type": impact_type,
                        "direction": "BUY" if is_buy else "SELL",
                        "transaction_id": txn_id
                    })

                return impacted_price

    def get_current_impact(self, symbol: str) -> Optional[Decimal]:
        """Get current impact for a symbol"""
        with self._lock:
            state = self._impact_states.get(symbol)
            if state:
                return state.current_impact
            return None

    def get_impact_state(self, symbol: str) -> Optional[ImpactSnapshot]:
        """Get complete impact state for a symbol"""
        with self._lock:
            return self._impact_states.get(symbol)

    def reset_impact(self, symbol: str):
        """Reset impact state for a symbol"""
        with self._lock:
            if symbol in self._impact_states:
                old_impact = self._impact_states[symbol].current_impact
                del self._impact_states[symbol]
                self.logger.info(f"Impact state reset for {symbol} - was {old_impact}")

    def get_all_impacts(self) -> Dict[str, ImpactSnapshot]:
        """Get all current impact states"""
        with self._lock:
            return self._impact_states.copy()

    def log_impact_summary(self):
        """Log summary of all current impacts"""
        with self._lock:
            if not self._impact_states:
                self.logger.info("No active impact states")
                return

            self.logger.info(f"=== Impact Summary for {len(self._impact_states)} symbols ===")
            for symbol, state in self._impact_states.items():
                impact_bps = state.current_impact * Decimal('10000')
                self.logger.info(f"{symbol}: {impact_bps:.2f} bps (vol: {state.trade_volume}/{state.bin_volume})")