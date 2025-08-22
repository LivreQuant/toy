# source/db/managers/portfolio_data.py
from typing import Dict, List
import traceback
from datetime import datetime
from decimal import Decimal
from source.simulation.managers.portfolio import Position
from source.db.managers.base_manager import BaseTableManager


class PortfolioDataManager(BaseTableManager):
    """Manager for portfolio data table operations"""

    async def load_book_data(self, book_id: str, timestamp_str: str) -> Dict[str, Position]:
        """Load book portfolio data from PostgreSQL using normalized schema"""
        await self.ensure_connection()

        try:
            async with self.pool.acquire() as conn:
                target_datetime = self._get_timestamp_str(timestamp_str)

                query = """
                    SELECT book_id, timestamp, symbol, quantity, currency, 
                           avg_price, mtm_value, sod_realized_pnl, itd_realized_pnl,
                           realized_pnl, unrealized_pnl
                    FROM exch_us_equity.portfolio_data 
                    WHERE book_id = $1 AND timestamp = $2
                """

                rows = await conn.fetch(query, book_id, target_datetime)

                # Build portfolio positions dictionary
                portfolio_data = {}
                processed_symbols = set()

                for row in rows:
                    symbol = row['symbol']

                    # Take only the most recent record for each symbol
                    if symbol not in processed_symbols:
                        portfolio_data[symbol] = Position(
                            symbol=symbol,
                            quantity=float(row['quantity']),
                            target_quantity=0,  # Will be calculated elsewhere
                            currency=row['currency'],
                            avg_price=float(row['avg_price']),
                            mtm_value=float(row['mtm_value']),
                            sod_realized_pnl=float(row['sod_realized_pnl']),
                            itd_realized_pnl=float(row['itd_realized_pnl']),
                            realized_pnl=float(row['realized_pnl']),
                            unrealized_pnl=float(row['unrealized_pnl'])
                        )
                        processed_symbols.add(symbol)

                self.logger.info(f"✅ Loaded portfolio data for {book_id}: {len(portfolio_data)} positions")
                return portfolio_data

        except Exception as e:
            self.logger.error(f"❌ Error loading portfolio data for {book_id}: {e}")
            return {}

    async def insert_simulation_data(self, data: List[Dict], book_id: str, timestamp: datetime) -> int:
        """Insert portfolio simulation data into normalized table"""
        await self.ensure_connection()

        if not data:
            return 0

        try:
            async with self.pool.acquire() as conn:
                # Insert into normalized portfolio_data table
                query = """
                    INSERT INTO exch_us_equity.portfolio_data (
                        book_id, timestamp, symbol, quantity, currency,
                        avg_price, mtm_value, sod_realized_pnl, itd_realized_pnl,
                        realized_pnl, unrealized_pnl
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                    ON CONFLICT (book_id, timestamp, symbol) DO UPDATE SET
                        quantity = EXCLUDED.quantity,
                        currency = EXCLUDED.currency,
                        avg_price = EXCLUDED.avg_price,
                        mtm_value = EXCLUDED.mtm_value,
                        sod_realized_pnl = EXCLUDED.sod_realized_pnl,
                        itd_realized_pnl = EXCLUDED.itd_realized_pnl,
                        realized_pnl = EXCLUDED.realized_pnl,
                        unrealized_pnl = EXCLUDED.unrealized_pnl
                """

                records = []
                for record in data:
                    records.append((
                        book_id,
                        timestamp,
                        record['symbol'],
                        Decimal(str(record.get('quantity', 0))),
                        record.get('currency', 'USD'),
                        Decimal(str(record.get('avg_price', 0))),
                        Decimal(str(record.get('mtm_value', 0))),
                        Decimal(str(record.get('sod_realized_pnl', 0))),
                        Decimal(str(record.get('itd_realized_pnl', 0))),
                        Decimal(str(record.get('realized_pnl', 0))),
                        Decimal(str(record.get('unrealized_pnl', 0)))
                    ))


                await conn.executemany(query, records)

                self.logger.info(f"✅ Inserted {len(records)} portfolio records for {book_id}")
                return len(records)

        except Exception as e:
            self.logger.error(f"❌ Error inserting portfolio simulation data: {e}")
            self.logger.error(f"❌ Full traceback: {traceback.format_exc()}")
            return 0
