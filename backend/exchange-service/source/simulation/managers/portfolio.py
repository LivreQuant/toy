# source/simulation/managers/portfolio.py
from dataclasses import dataclass
from typing import Dict, Optional
from datetime import datetime
from decimal import Decimal
from source.utils.timezone_utils import to_iso_string
from source.simulation.managers.utils import TrackingManager


@dataclass
class Position:
    symbol: str
    quantity: Decimal
    target_quantity: Decimal
    currency: str
    avg_price: Decimal
    mtm_value: Decimal
    sod_realized_pnl: Decimal = Decimal('0')
    itd_realized_pnl: Decimal = Decimal('0')
    realized_pnl: Decimal = Decimal('0')
    unrealized_pnl: Decimal = Decimal('0')

    def __init__(self, symbol: str, quantity: float, target_quantity: float, avg_price: float,
                 mtm_value: float, currency: str, sod_realized_pnl: float = 0, itd_realized_pnl: float = 0,
                 realized_pnl: float = 0, unrealized_pnl: float = 0):
        self.symbol = symbol
        self.quantity = Decimal(str(quantity))
        self.target_quantity = Decimal(str(target_quantity))
        self.currency = currency
        self.avg_price = Decimal(str(avg_price))
        self.mtm_value = Decimal(str(mtm_value))
        self.sod_realized_pnl = Decimal(str(sod_realized_pnl))
        self.itd_realized_pnl = Decimal(str(itd_realized_pnl))
        self.realized_pnl = Decimal(str(realized_pnl))
        self.unrealized_pnl = Decimal(str(unrealized_pnl))

    def to_dict(self) -> Dict:
        return {
            'symbol': self.symbol,
            'quantity': str(self.quantity),
            'target_quantity': str(self.target_quantity),
            'currency': self.currency,
            'avg_price': str(self.avg_price),
            'mtm_value': str(self.mtm_value),
            'sod_realized_pnl': str(self.sod_realized_pnl),
            'itd_realized_pnl': str(self.itd_realized_pnl),
            'realized_pnl': str(self.realized_pnl),
            'unrealized_pnl': str(self.unrealized_pnl),
        }


class PortfolioManager(TrackingManager):
    def __init__(self, tracking: bool = True):
        headers = [
            'timestamp', 'symbol', 'quantity', 'target_quantity', 'currency', 'avg_price', 'mtm_value',
            'sod_realized_pnl', 'itd_realized_pnl', 'realized_pnl', 'unrealized_pnl',
        ]

        super().__init__(
            manager_name="PortfolioManager",
            table_name="portfolio_data",
            headers=headers,
            tracking=tracking
        )

        # Positions storage
        self.positions: Dict[str, Position] = {}

        # Previous positions storage
        self.previous_positions: Dict[str, Position] = {}

    def _calculate_target_quantity(self, symbol: str, current_quantity: Decimal) -> Decimal:
        """Calculate target quantity based on current position and open orders"""
        from source.orchestration.app_state.state_manager import app_state

        target_quantity = current_quantity

        # Get the specific market for this symbol
        exchange = app_state.exchange
        if exchange:
            try:
                market = exchange.get_market(symbol)
                if market:
                    pending_qty = market.get_pending_quantity()  # This works because market is symbol-specific
                    target_quantity += Decimal(str(pending_qty))
            except Exception as e:
                raise ValueError(f"Error getting pending quantity for {symbol}: {e}")
        else:
            raise ValueError(f"Error getting pending quantity for {symbol}: No Exchange")

        return target_quantity

    def save_current_as_previous(self) -> None:
        """Save current positions as previous positions before updating with new data"""
        with self._lock:
            self.previous_positions = {
                symbol: Position(
                    symbol=position.symbol,
                    quantity=position.quantity,
                    target_quantity=position.target_quantity,
                    currency=position.currency,
                    avg_price=position.avg_price,
                    mtm_value=position.mtm_value,
                    sod_realized_pnl=position.sod_realized_pnl,
                    itd_realized_pnl=position.itd_realized_pnl,
                    realized_pnl=position.realized_pnl,
                    unrealized_pnl=position.unrealized_pnl
                )
                for symbol, position in self.positions.items()
            }

    def initialize_portfolio(self, positions: Dict[str, Position], timestamp: datetime) -> None:
        """Initialize portfolio with last snapshot positions - NO FILE WRITING"""
        with self._lock:
            # Check if positions are already Position objects or need to be converted
            if positions:
                first_value = next(iter(positions.values()))
                if hasattr(first_value, 'symbol'):  # It's already a Position object
                    self.logger.info("📦 Received Position objects directly")
                    self.positions = positions.copy()
                else:
                    # Convert from dictionary format to Position objects
                    self.logger.info("📦 Converting dictionary data to Position objects")
                    converted_positions = {}
                    for symbol, pos_data in positions.items():
                        converted_positions[symbol] = Position(
                            symbol=pos_data['symbol'],
                            quantity=float(pos_data['quantity']),
                            target_quantity=float(pos_data.get('target_quantity', 0)),
                            currency=pos_data['currency'],
                            avg_price=float(pos_data['avg_price']),
                            mtm_value=float(pos_data['mtm_value']),
                            sod_realized_pnl=float(pos_data.get('sod_realized_pnl', 0)),
                            itd_realized_pnl=float(pos_data.get('itd_realized_pnl', 0)),
                            realized_pnl=float(pos_data.get('realized_pnl', 0)),
                            unrealized_pnl=float(pos_data.get('unrealized_pnl', 0))
                        )
                    self.positions = converted_positions
            else:
                self.positions = {}

            # Update target quantities based on market orders
            from source.orchestration.app_state.state_manager import app_state
            exchange = app_state.exchange

            if exchange:
                for position in self.positions.values():
                    # Calculate target including any pending market orders
                    position.target_quantity = self._calculate_target_quantity(
                        position.symbol,
                        position.quantity
                    )

            self.save_current_as_previous()
            # ✅ NO FILE WRITING during initialization

    def _prepare_position_data(self, position: Position, timestamp: datetime) -> Dict:
        """Prepare position data for storage"""

        return {
            'timestamp': to_iso_string(timestamp),
            'symbol': position.symbol,
            'quantity': str(position.quantity),
            'target_quantity': str(position.target_quantity),
            'currency': position.currency,
            'avg_price': str(position.avg_price),
            'mtm_value': str(position.mtm_value),
            'sod_realized_pnl': str(position.sod_realized_pnl),
            'itd_realized_pnl': str(position.itd_realized_pnl),
            'realized_pnl': str(position.realized_pnl),
            'unrealized_pnl': str(position.unrealized_pnl),
        }

    def update_position(self, symbol: str, quantity: Decimal, currency: str, price: Decimal) -> None:
        """Update position with trade"""
        with self._lock:
            if symbol not in self.positions:
                self.positions[symbol] = Position(
                    symbol=symbol,
                    quantity=0,
                    target_quantity=0,
                    currency=currency,
                    avg_price=0,
                    mtm_value=0,
                )

            position = self.positions[symbol]
            old_quantity = position.quantity
            old_avg_price = position.avg_price

            new_quantity = old_quantity + quantity

            if new_quantity == Decimal('0'):
                position.avg_price = Decimal('0')
            elif quantity * old_quantity >= Decimal('0'):
                position_value = old_quantity * old_avg_price + quantity * price
                position.avg_price = round(position_value / new_quantity, 2)
            else:
                # closed_quantity = min(abs(quantity), abs(old_quantity))
                pass

            position.quantity = new_quantity
            # Update target quantity based on current open orders
            position.target_quantity = self._calculate_target_quantity(symbol, new_quantity)

            if position.quantity != Decimal('0'):
                position.unrealized_pnl = round((price - position.avg_price) * position.quantity, 2)
            else:
                position.unrealized_pnl = Decimal('0')

            # Write position update to storage
            if self.tracking:
                from source.orchestration.app_state.state_manager import app_state
                market_timestamp = app_state.get_next_timestamp()
                if market_timestamp:
                    position_data = [self._prepare_position_data(position, market_timestamp)]
                    self.write_to_storage(position_data, timestamp=market_timestamp)
                else:
                    self.logger.warning(f"⚠️ No market timestamp for position update {symbol}")

    def update_portfolio(self, market_prices: Dict[str, Decimal]) -> None:
        """Update position valuations with new market prices"""
        with self._lock:
            self.logger.info("=" * 80)
            self.logger.info("💼 PORTFOLIO UPDATE STARTING")
            self.logger.info("=" * 80)
            self.logger.info(f"📊 Received {len(market_prices)} price updates")
            self.logger.info(f"📊 Current positions: {len(self.positions)}")

            # Log the price updates
            for symbol, price in market_prices.items():
                self.logger.info(f"   📈 {symbol}: ${price}")

            # Log current positions before update
            self.logger.info(f"📊 POSITIONS BEFORE UPDATE:")
            for symbol, position in self.positions.items():
                self.logger.info(
                    f"   📦 {symbol}: qty={position.quantity}, avg_price=${position.avg_price}, mtm=${position.mtm_value}")

            for symbol, price in market_prices.items():
                if symbol in self.positions:
                    position = self.positions[symbol]
                    old_mtm = position.mtm_value
                    old_unrealized = position.unrealized_pnl

                    last_update_price = Decimal(str(price)) if isinstance(price, float) else price
                    position.realized_pnl = position.sod_realized_pnl + position.itd_realized_pnl

                    if position.quantity != Decimal('0'):
                        position.unrealized_pnl = round((last_update_price - position.avg_price) * position.quantity, 2)
                    else:
                        position.unrealized_pnl = Decimal('0')

                    position.mtm_value = round(position.quantity * last_update_price, 2)

                    # Log the changes
                    self.logger.info(f"📈 UPDATED {symbol}:")
                    self.logger.info(f"   Price: ${last_update_price}")
                    self.logger.info(f"   MTM: ${old_mtm} → ${position.mtm_value}")
                    self.logger.info(f"   Unrealized P&L: ${old_unrealized} → ${position.unrealized_pnl}")
                else:
                    self.logger.warning(f"⚠️ Price update for {symbol} but no position exists")

            # Log positions after update
            self.logger.info(f"📊 POSITIONS AFTER UPDATE:")
            for symbol, position in self.positions.items():
                self.logger.info(
                    f"   📦 {symbol}: qty={position.quantity}, avg_price=${position.avg_price}, mtm=${position.mtm_value}, unrealized_pnl=${position.unrealized_pnl}")

            self.logger.info("✅ PORTFOLIO UPDATE COMPLETE")
            self.logger.info("=" * 80)

            # Write all positions to storage
            if self.tracking:
                from source.orchestration.app_state.state_manager import app_state
                market_timestamp = app_state.get_next_timestamp()
                if market_timestamp:
                    all_positions_data = [
                        self._prepare_position_data(position, market_timestamp)
                        for position in self.positions.values()
                    ]
                    if all_positions_data:
                        self.write_to_storage(all_positions_data, timestamp=market_timestamp)
                        self.logger.info(f"📁 Wrote {len(all_positions_data)} positions to storage")
                    else:
                        self.logger.debug("📁 No positions to write - skipping storage")
                else:
                    self.logger.warning(f"⚠️ No market timestamp for portfolio update")

    def compute_portfolio_balances(self, current: bool = True) -> Dict[str, Decimal]:
        """Compute portfolio value by currency including mark-to-market value and unrealized PNL

        Args:
            current: If True, use current positions, if False use previous positions
        """
        from source.orchestration.app_state.state_manager import app_state
        if not app_state.equity_manager:
            raise ValueError("No market data manager available")

        portfolio_by_currency = {}
        positions = self.get_all_positions(current=current)  # Use the current flag here

        for position in positions.values():
            currency = position.currency

            # Calculate mark-to-market value
            mtm_value = Decimal(str(position.mtm_value))

            # Total position value is MTM
            position_value = mtm_value

            if currency not in portfolio_by_currency:
                portfolio_by_currency[currency] = Decimal('0')

            portfolio_by_currency[currency] += position_value

        return portfolio_by_currency

    def get_position(self, symbol: str, current: bool = True) -> Optional[Position]:
        """Get position for a symbol, either current or previous based on flag"""
        with self._lock:
            positions_dict = self.positions if current else self.previous_positions
            return positions_dict.get(symbol)

    def get_all_positions(self, current: bool = True) -> Dict[str, Position]:
        """Get all positions, either current or previous based on flag"""
        with self._lock:
            positions_dict = self.positions if current else self.previous_positions
            return positions_dict.copy()