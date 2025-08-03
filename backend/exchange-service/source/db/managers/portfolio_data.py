# source/db/managers/portfolio_data.py
from typing import Dict, List
from datetime import datetime
from decimal import Decimal
from source.simulation.managers.portfolio import Position
from source.db.managers.base_manager import BaseTableManager


class PortfolioDataManager(BaseTableManager):
    """Manager for portfolio data table operations"""

    async def load_user_data(self, user_id: str, timestamp_str: str) -> Dict[str, Position]:
        """Load user portfolio data from PostgreSQL using normalized schema"""
        await self.ensure_connection()

        try:
            async with self.pool.acquire() as conn:
                query = """
                    SELECT user_id, timestamp, symbol, quantity, currency, 
                           avg_price, mtm_value, sod_realized_pnl, itd_realized_pnl,
                           realized_pnl, unrealized_pnl
                    FROM exch_us_equity.portfolio_data 
                    WHERE user_id = $1 AND DATE(timestamp) = DATE($2::timestamp)
                    ORDER BY timestamp DESC
                """

                # Parse timestamp string properly and convert to datetime object
                try:
                    from datetime import datetime

                    if '_' in timestamp_str and len(timestamp_str) >= 13:
                        # Format: "20240109_1932" -> datetime object
                        date_part = timestamp_str[:8]
                        time_part = timestamp_str[9:]
                        date_str = f"{date_part[:4]}-{date_part[4:6]}-{date_part[6:8]}"
                        if len(time_part) == 4:
                            time_str = f"{time_part[:2]}:{time_part[2:]}:00"
                            timestamp_date = datetime.strptime(f"{date_str} {time_str}", '%Y-%m-%d %H:%M:%S')
                        else:
                            timestamp_date = datetime.strptime(f"{date_str} 00:00:00", '%Y-%m-%d %H:%M:%S')
                    elif len(timestamp_str) == 8:
                        # Format: "20240109" -> datetime object
                        date_str = f"{timestamp_str[:4]}-{timestamp_str[4:6]}-{timestamp_str[6:8]}"
                        timestamp_date = datetime.strptime(f"{date_str} 00:00:00", '%Y-%m-%d %H:%M:%S')
                    else:
                        # Try to parse as ISO format
                        timestamp_date = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))

                except Exception as e:
                    self.logger.warning(f"⚠️ Error parsing timestamp {timestamp_str}: {e}")
                    timestamp_date = datetime(1970, 1, 1)  # Fallback datetime object

                rows = await conn.fetch(query, user_id, timestamp_date)

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

                self.logger.info(f"✅ Loaded portfolio data for {user_id}: {len(portfolio_data)} positions")
                return portfolio_data

        except Exception as e:
            self.logger.error(f"❌ Error loading portfolio data for {user_id}: {e}")
            return {}

    async def insert_simulation_data(self, data: List[Dict], user_id: str, timestamp: datetime) -> int:
        """Insert portfolio simulation data into normalized table"""
        await self.ensure_connection()

        if not data:
            return 0

        try:
            async with self.pool.acquire() as conn:
                # Insert into normalized portfolio_data table
                query = """
                    INSERT INTO exch_us_equity.portfolio_data (
                        user_id, timestamp, symbol, quantity, currency,
                        avg_price, mtm_value, sod_realized_pnl, itd_realized_pnl,
                        realized_pnl, unrealized_pnl
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                    ON CONFLICT (user_id, timestamp, symbol) DO UPDATE SET
                        quantity = EXCLUDED.quantity,
                        currency = EXCLUDED.currency,
                        avg_price = EXCLUDED.avg_price,
                        mtm_value = EXCLUDED.mtm_value,
                        sod_realized_pnl = EXCLUDED.sod_realized_pnl,
                        itd_realized_pnl = EXCLUDED.itd_realized_pnl,
                        realized_pnl = EXCLUDED.realized_pnl,
                        unrealized_pnl = EXCLUDED.unrealized_pnl
                """

                import uuid
                records = []
                for record in data:
                    records.append((
                        user_id,
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

                self.logger.info(f"✅ Inserted {len(records)} portfolio records for {user_id}")
                return len(records)

        except Exception as e:
            self.logger.error(f"❌ Error inserting portfolio simulation data: {e}")
            import traceback
            self.logger.error(f"❌ Full traceback: {traceback.format_exc()}")
            return 0
