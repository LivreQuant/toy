from threading import RLock
from typing import Dict, Optional, List
from datetime import datetime
import logging
from dataclasses import dataclass
from decimal import Decimal
from source.simulation.core.interfaces.exchange import Exchange_ABC
from source.simulation.managers.utils import CallbackManager
from source.simulation.managers.fx import FXRate


@dataclass
class EquityState:
    last_update_time: datetime
    last_currency: str
    last_price: Decimal
    last_volume: int


@dataclass
class EquityBar:
    symbol: str
    timestamp: str
    currency: str
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int
    count: int
    vwap: Decimal
    vwas: Decimal
    vwav: Decimal

    def __init__(self, symbol: str, timestamp: str, currency: str, open: float, high: float,
                 low: float, close: float, volume: int, count: int, vwap: float, vwas: float, vwav: float):
        self.symbol = symbol
        self.timestamp = timestamp
        self.currency = currency
        self.open = Decimal(str(open))
        self.high = Decimal(str(high))
        self.low = Decimal(str(low))
        self.close = Decimal(str(close))
        self.volume = volume
        self.count = count
        self.vwap = Decimal(str(vwap))
        self.vwas = Decimal(str(vwas))
        self.vwav = Decimal(str(vwav))


class EquityManager(CallbackManager[List[Dict]]):
    """
    Manages equity data and triggers market data processing.

    Single Responsibility: Handle equity data storage, state management, and trigger processing.
    """

    def __init__(self, tracking: bool = False, exchange: Optional[Exchange_ABC] = None,
                 exchange_group_manager=None):
        CallbackManager.__init__(self)

        self._lock = RLock()
        self._state_lock = RLock()
        self.logger = logging.getLogger(self.__class__.__name__)
        self._exchange = exchange
        self._symbol_state: Dict[str, EquityState] = {}
        self.exchange_group_manager = exchange_group_manager

    def set_exchange(self, exchange: Exchange_ABC) -> None:
        """Set the exchange reference"""
        self._exchange = exchange

    def _update_symbol_states(self, equity_bars: List[EquityBar]) -> None:
        """Update internal symbol states with new equity data"""
        with self._state_lock:
            for bar in equity_bars:
                self._symbol_state[bar.symbol] = EquityState(
                    last_update_time=datetime.fromisoformat(bar.timestamp),
                    last_currency=bar.currency,
                    last_price=Decimal(str(bar.close)),
                    last_volume=bar.volume
                )

    def _trigger_market_data_processing(self, equity_bars: List[EquityBar], fx: Optional[List[FXRate]]) -> None:
        """Trigger market data processing - multi-user mode only"""
        try:
            from source.orchestration.processors.market_data_processor import MarketDataProcessor
            processor = MarketDataProcessor(self.exchange_group_manager)
            processor.process_market_data_bin(equity_bars, fx)

        except Exception as e:
            self.logger.error(f"❌ Error in multi-user market data processing: {e}")
            raise

    def _prepare_snapshot_data(self, equity_bars: List[EquityBar]) -> List[Dict]:
        """Prepare equity data for callbacks"""
        from source.utils.timezone_utils import to_iso_string
        snapshot_data = []
        for bar in equity_bars:
            event = {
                'timestamp': to_iso_string(bar.timestamp) if isinstance(bar.timestamp, datetime) else bar.timestamp,
                'symbol': bar.symbol,
                'currency': bar.currency,
                'open': str(bar.open),
                'high': str(bar.high),
                'low': str(bar.low),
                'close': str(bar.close),
                'vwap': str(bar.vwap),
                'vwas': str(bar.vwas),
                'vwav': str(bar.vwav),
                'volume': bar.volume,
                'count': bar.count
            }
            snapshot_data.append(event)
        return snapshot_data

    def insert_last_snap_equity(self, equity: List[Dict], timestamp: datetime) -> None:
        """Set the last snapshot equity state for symbols and FX rates - used during initialization"""
        self.logger.info(f"📊 Initializing Last Snap equity state for {len(equity)} symbols")

        # Handle equity states
        with self._state_lock:
            for state in equity:
                self._symbol_state[state['symbol']] = EquityState(
                    last_update_time=timestamp,
                    last_currency=state['currency'],
                    last_price=Decimal(str(state['last_price'])),
                    last_volume=int(state['last_volume'])
                )

    def get_last_price(self, symbol: str) -> Optional[Decimal]:
        """Get the last known price for a symbol"""
        with self._state_lock:
            state = self._symbol_state.get(symbol)
            if state is not None:
                return state.last_price
            return None

    def register_update_callback(self, callback):
        """
        Register callback for equity updates.

        NOTE: In the MASTER TRIGGER pattern, only the session service should register here.
        Other managers are updated directly in the MarketDataProcessor.
        """
        self.logger.info(
            f"📡 Registering callback: {callback.__name__ if hasattr(callback, '__name__') else 'anonymous'}")
        self.register_callback(callback)

    def get_equity_stats(self) -> Dict:
        """Get statistics about equity data processing"""
        with self._state_lock:
            return {
                'symbols_tracked': len(self._symbol_state),
                'symbols': list(self._symbol_state.keys()),
                'last_update_times': {
                    symbol: state.last_update_time.isoformat()
                    for symbol, state in self._symbol_state.items()
                },
                'current_prices': {
                    symbol: str(state.last_price)
                    for symbol, state in self._symbol_state.items()
                }
            }

    def set_exchange_group_manager(self, exchange_group_manager):
        """Set the exchange group manager for multi-user mode"""
        self.exchange_group_manager = exchange_group_manager
        self.logger.info("📡 Multi-user mode enabled - will broadcast to all users")

    def record_equity_data_batch(self, equity_bars: List[EquityBar], fx: Optional[List[FXRate]] = None) -> None:
        """Process incoming equity data batch for all users"""
        try:
            self.logger.info(f"🚀 EQUITY MANAGER PROCESSING {len(equity_bars)} EQUITY BARS")

            if not equity_bars:
                self.logger.debug("Received empty equity data batch - likely a health check")
                return

            # Step 1: Update internal equity symbol states
            self.logger.info("📊 STEP 1: Updating symbol states...")
            self._update_symbol_states(equity_bars)

            # Step 2: Trigger multi-user market data processing
            self.logger.info("🔄 STEP 2: Triggering market data processing...")
            self._trigger_market_data_processing(equity_bars, fx)

            # Step 3: Notify callbacks (session service) with equity data
            self.logger.info("📡 STEP 3: Preparing to notify callbacks...")
            snapshot_data = self._prepare_snapshot_data(equity_bars)
            self.logger.info(
                f"🔥 STEP 3: About to notify {len(self._callbacks)} callbacks with {len(snapshot_data)} records...")
            self._notify_callbacks(snapshot_data)

            self.logger.info(f"✅ EQUITY MANAGER PROCESSING COMPLETE")

        except Exception as e:
            self.logger.error(f"❌ Error recording equity data batch: {e}", exc_info=True)
            raise ValueError(f"Error recording equity data batch: {e}")
