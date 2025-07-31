# source/simulation/managers/returns.py
from dataclasses import dataclass
from typing import Dict, List, Optional
from datetime import datetime
from decimal import Decimal
from collections import defaultdict

from source.simulation.managers.returns_utils import ReturnsCalculator
from source.simulation.managers.utils import TrackingManager


@dataclass
class ReturnMetrics:
    emv: Decimal
    bmv: Decimal
    bmv_book: Decimal
    cf: Decimal
    periodic_return_subcategory: Decimal
    cumulative_return_subcategory: Decimal
    contribution_percentage: Decimal
    periodic_return_contribution: Decimal
    cumulative_return_contribution: Decimal


class ReturnsManager(TrackingManager, ReturnsCalculator):
    VALID_CATEGORIES = ["BOOK", "CASH_EQUITY", "LONG_SHORT"]

    def __init__(self, tracking: bool = False):
        headers = [
            'timestamp', 'category', 'subcategory',
            'emv', 'bmv', 'bmv_book', 'cf',
            'periodic_return_subcategory', 'cumulative_return_subcategory',
            'contribution_percentage',
            'periodic_return_contribution', 'cumulative_return_contribution',
        ]

        super().__init__(
            manager_name="ReturnsManager",
            table_name="return_data",
            headers=headers,
            tracking=tracking
        )

        self.returns: Dict[str, Dict[str, Decimal]] = {}
        self.timestamp: datetime = datetime.now()

        # History of returns
        self.return_history: Dict[str, Dict[str, List[tuple[datetime, ReturnMetrics]]]] = defaultdict(
            lambda: defaultdict(list))

        # Period baselines
        self.period_baselines: Dict[str, Dict[str, Dict[str, Dict[str, any]]]] = {}

    def compute_return(
            self,
            ending_value: Decimal,
            beginning_value: Decimal,
            cash_flow: Decimal
    ) -> Decimal:
        """Compute single period return using (EMV)/(BMV + CF) - 1 formula"""
        denominator = beginning_value + cash_flow
        if denominator == Decimal('0'):
            return Decimal('0')
        return (ending_value / denominator) - Decimal('1')

    def compute_geometric_return(self, returns: List[Decimal]) -> Decimal:
        """Compute geometric cumulative return from a list of periodic returns"""
        if not returns:
            return Decimal('0')

        cumulative = Decimal('1')
        for r in returns:
            cumulative *= (Decimal('1') + r)
        return cumulative - Decimal('1')

    def update_returns_for_category(
            self,
            category: str,
            subcategory: str,
            current_timestamp: datetime,
            values: Dict[str, Decimal]
    ) -> None:
        """Update returns and metrics for a category/subcategory"""
        with self._lock:
            # Calculate contribution percentage
            contribution_percentage = values['bmv'] / values['bmv_book'] if values['bmv_book'] != 0 else Decimal('0')

            # Calculate periodic returns
            periodic_return_subcategory = self.compute_return(
                values['emv'], values['bmv'], values['cf']
            )
            periodic_return_contribution = periodic_return_subcategory * contribution_percentage

            # Get historical returns for cumulative calculations
            historical_returns = [
                metrics.periodic_return_subcategory
                for _, metrics in self.return_history[category][subcategory]
            ]
            historical_contribution_returns = [
                metrics.periodic_return_contribution
                for _, metrics in self.return_history[category][subcategory]
            ]

            # Add current return for cumulative calculation
            historical_returns.append(periodic_return_subcategory)
            historical_contribution_returns.append(periodic_return_contribution)

            # Calculate cumulative returns
            cumulative_return_subcategory = self.compute_geometric_return(historical_returns)
            cumulative_return_contribution = self.compute_geometric_return(historical_contribution_returns)

            # Create metrics object
            metrics = ReturnMetrics(
                emv=values['emv'],
                bmv=values['bmv'],
                bmv_book=values['bmv_book'],
                cf=values['cf'],
                periodic_return_subcategory=periodic_return_subcategory,
                cumulative_return_subcategory=cumulative_return_subcategory,
                contribution_percentage=contribution_percentage,
                periodic_return_contribution=periodic_return_contribution,
                cumulative_return_contribution=cumulative_return_contribution
            )

            # Update returns and history
            if category not in self.returns:
                self.returns[category] = {}
            self.returns[category][subcategory] = metrics
            self.return_history[category][subcategory].append((current_timestamp, metrics))

            # Store for batch write
            if self.tracking:
                self._store_return_data(current_timestamp, category, subcategory, metrics)

    def _store_return_data(self, timestamp: datetime, category: str, subcategory: str, metrics: ReturnMetrics) -> None:
        """Store return data for batch writing"""
        if not hasattr(self, '_pending_returns'):
            self._pending_returns = []

        from source.utils.timezone_utils import to_iso_string
        return_data = {
            'timestamp': to_iso_string(timestamp),
            'category': category,
            'subcategory': subcategory,
            'emv': str(metrics.emv),
            'bmv': str(metrics.bmv),
            'bmv_book': str(metrics.bmv_book),
            'cf': str(metrics.cf),
            'periodic_return_subcategory': str(metrics.periodic_return_subcategory),
            'cumulative_return_subcategory': str(metrics.cumulative_return_subcategory),
            'contribution_percentage': str(metrics.contribution_percentage),
            'periodic_return_contribution': str(metrics.periodic_return_contribution),
            'cumulative_return_contribution': str(metrics.cumulative_return_contribution)
        }

        self._pending_returns.append(return_data)

    def compute_all_returns(self, timestamp: datetime) -> None:
        """Compute and update all return categories"""
        from source.orchestration.app_state.state_manager import app_state
        if not app_state.cash_flow_manager:
            raise ValueError("No cash flow manager available")

        # Clear cash flows at start of new iteration
        app_state.cash_flow_manager.clear_current_flows()

        with self._lock:
            self.timestamp = timestamp

            try:
                return_computations = []

                if hasattr(self, 'compute_periodic_book_return'):
                    return_computations.append(self.compute_periodic_book_return)
                else:
                    self.logger.error("❌ compute_periodic_book_return method not found")

                if hasattr(self, 'compute_periodic_cash_equity_return'):
                    return_computations.append(self.compute_periodic_cash_equity_return)
                else:
                    self.logger.error("❌ compute_periodic_cash_equity_return method not found")

                if hasattr(self, 'compute_periodic_long_short_return'):
                    return_computations.append(self.compute_periodic_long_short_return)
                else:
                    self.logger.error("❌ compute_periodic_long_short_return method not found")

                for compute_return in return_computations:
                    category, components = compute_return()

                    # Process regular subcategories
                    total_emv = Decimal('0')
                    total_bmv = Decimal('0')
                    total_cf = Decimal('0')
                    bmv_book = Decimal('0')

                    for component_dict in components:
                        for subcategory, values in component_dict.items():
                            self.update_returns_for_category(
                                category=category,
                                subcategory=subcategory,
                                current_timestamp=timestamp,
                                values=values
                            )

                            # Accumulate totals
                            total_emv += values['emv']
                            total_bmv += values['bmv']
                            total_cf += values['cf']
                            bmv_book = values['bmv_book']

                    # Create and process TOTAL subcategory
                    total_values = {
                        'emv': total_emv,
                        'bmv': total_bmv,
                        'bmv_book': bmv_book,
                        'cf': total_cf
                    }

                    self.update_returns_for_category(
                        category=category,
                        subcategory='TOTAL',
                        current_timestamp=timestamp,
                        values=total_values
                    )

            except Exception as e:
                self.logger.error(f"❌ Error in return computations: {e}")
                raise

        # Write all returns to storage
        if self.tracking:
            self._flush_returns_to_storage()

    def _flush_returns_to_storage(self):
        """Write all accumulated returns to storage"""
        if hasattr(self, '_pending_returns') and self._pending_returns:
            self.write_to_storage(self._pending_returns, timestamp=self.timestamp)
            self.logger.info(f"📁 Wrote {len(self._pending_returns)} return records to storage")
            self._pending_returns = []

    def initialize_period_baselines(self, returns_data: Dict, timestamp: datetime) -> None:
        """Initialize period baseline returns from last snapshot - no SOD file writing"""
        with self._lock:
            if not returns_data or 'returns' not in returns_data:
                self.logger.info("No period baseline returns data to initialize")
                return

            period_starts = returns_data['returns']
            self.logger.info(f"🔍 Processing {len(period_starts)} period baseline entries")

            # Build period baselines
            for period_data in period_starts:
                period_type = period_data['period_type']
                category = period_data['category']
                subcategory = period_data['subcategory']

                if period_type not in self.period_baselines:
                    self.period_baselines[period_type] = {}
                if category not in self.period_baselines[period_type]:
                    self.period_baselines[period_type][category] = {}

                baseline_timestamp = timestamp.isoformat()

                self.period_baselines[period_type][category][subcategory] = {
                    'cumulative_return_subcategory': Decimal(
                        str(period_data.get('cumulative_return_subcategory', 0.0))),
                    'cumulative_return_contribution': Decimal(
                        str(period_data.get('cumulative_return_contribution', 0.0))),
                    'timestamp': baseline_timestamp,
                    'period_type': period_type
                }

            self.logger.info(f"✓ Initialized period baselines for {len(self.period_baselines)} period types")

    def get_period_return(self, period_type: str, category: str, subcategory: str) -> Dict[str, Decimal]:
        """Calculate period-to-date returns (WTD, MTD, QTD, YTD)"""
        with self._lock:
            # Get current cumulative returns
            current_returns = self.returns.get(category, {}).get(subcategory)
            if not current_returns:
                return {
                    'period_return_subcategory': Decimal('0'),
                    'period_return_contribution': Decimal('0')
                }

            # Get baseline for this period
            baseline = self.period_baselines.get(period_type, {}).get(category, {}).get(subcategory)
            if not baseline:
                # No baseline means period started from zero
                return {
                    'period_return_subcategory': current_returns.cumulative_return_subcategory,
                    'period_return_contribution': current_returns.cumulative_return_contribution
                }

            # Calculate period returns
            period_return_subcategory = (current_returns.cumulative_return_subcategory -
                                         baseline['cumulative_return_subcategory'])
            period_return_contribution = (current_returns.cumulative_return_contribution -
                                          baseline['cumulative_return_contribution'])

            return {
                'period_return_subcategory': period_return_subcategory,
                'period_return_contribution': period_return_contribution,
                'baseline_timestamp': baseline['timestamp']
            }

    def get_returns(
            self,
            category: str,
            subcategory: str,
            start_time: Optional[datetime] = None,
            end_time: Optional[datetime] = None
    ) -> List[tuple[datetime, ReturnMetrics]]:
        """Get historical returns for a category/subcategory within time range"""
        with self._lock:
            returns = self.return_history[category][subcategory]
            if start_time and end_time:
                returns = [(t, m) for t, m in returns if start_time <= t <= end_time]
            return returns.copy()

    def get_latest_returns(
            self,
            category: str,
            subcategory: str
    ) -> Optional[tuple[datetime, ReturnMetrics]]:
        """Get most recent returns for a category/subcategory"""
        with self._lock:
            returns = self.return_history[category][subcategory]
            return returns[-1] if returns else None

    def get_all_returns(self) -> Dict[str, Dict[str, ReturnMetrics]]:
        """Get all current returns"""
        with self._lock:
            return self.returns.copy()

    def get_all_period_returns(self) -> Dict[str, Dict[str, Dict[str, Dict[str, Decimal]]]]:
        """Get all period returns for all categories/subcategories"""
        period_returns = {}

        for period_type in ['WTD', 'MTD', 'QTD', 'YTD']:
            period_returns[period_type] = {}

            for category in self.VALID_CATEGORIES:
                if category in self.returns:
                    period_returns[period_type][category] = {}

                    for subcategory in self.returns[category]:
                        period_returns[period_type][category][subcategory] = self.get_period_return(
                            period_type, category, subcategory
                        )

        return period_returns