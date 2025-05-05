import logging
import time
import json
from typing import Dict, Any, List, Optional

from source.db.connection_pool import DatabasePool
from source.models.portfolio import Portfolio
from source.utils.metrics import track_db_operation, track_order_created, track_user_order


logger = logging.getLogger('portfolio_repository')


class PortfolioRepository:
    def __init__(self):
        self.db_pool = DatabasePool()

    async def create_portfolio(self, portfolio: Portfolio) -> bool:
        """Create a new portfolio"""
        pool = await self.db_pool.get_pool()
        
        query = """
        INSERT INTO trading.portfolios (
            portfolio_id, user_id, name, initial_capital, 
            risk_level, sector, status, created_at, updated_at
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
        """
        
        try:
            async with pool.acquire() as conn:
                await conn.execute(
                    query,
                    portfolio.portfolio_id,
                    portfolio.user_id,
                    portfolio.name,
                    portfolio.initial_capital,
                    portfolio.risk_level,
                    portfolio.sector,
                    portfolio.status,
                    portfolio.created_at,
                    portfolio.updated_at
                )
            return True
        except Exception as e:
            logger.error(f"Error creating portfolio: {e}")
            return False

    async def get_portfolio(self, portfolio_id: str) -> Optional[Portfolio]:
        """Retrieve a portfolio by ID"""
        pool = await self.db_pool.get_pool()
        
        query = """
        SELECT * FROM trading.portfolios 
        WHERE portfolio_id = $1
        """
        
        try:
            async with pool.acquire() as conn:
                row = await conn.fetchrow(query, portfolio_id)
                
                if not row:
                    return None
                
                return Portfolio(
                    portfolio_id=row['portfolio_id'],
                    user_id=row['user_id'],
                    name=row['name'],
                    initial_capital=row['initial_capital'],
                    risk_level=row['risk_level'],
                    sector=row['sector'],
                    status=row['status'],
                    created_at=row['created_at'].timestamp(),
                    updated_at=row['updated_at'].timestamp()
                )
        except Exception as e:
            logger.error(f"Error retrieving portfolio: {e}")
            return None

    async def update_portfolio(self, portfolio: Portfolio) -> bool:
        """Update an existing portfolio"""
        pool = await self.db_pool.get_pool()
        
        query = """
        UPDATE trading.portfolios
        SET name = $2, 
            initial_capital = $3, 
            risk_level = $4, 
            sector = $5, 
            status = $6, 
            updated_at = $7
        WHERE portfolio_id = $1
        """
        
        try:
            async with pool.acquire() as conn:
                await conn.execute(
                    query,
                    portfolio.portfolio_id,
                    portfolio.name,
                    portfolio.initial_capital,
                    portfolio.risk_level,
                    portfolio.sector,
                    portfolio.status,
                    time.time()
                )
            return True
        except Exception as e:
            logger.error(f"Error updating portfolio: {e}")
            return False

    async def get_user_portfolios(self, user_id: str) -> List[Portfolio]:
        """Retrieve all portfolios for a user"""
        pool = await self.db_pool.get_pool()
        
        query = """
        SELECT * FROM trading.portfolios 
        WHERE user_id = $1
        ORDER BY created_at DESC
        """
        
        try:
            async with pool.acquire() as conn:
                rows = await conn.fetch(query, user_id)
                
                return [
                    Portfolio(
                        portfolio_id=row['portfolio_id'],
                        user_id=row['user_id'],
                        name=row['name'],
                        initial_capital=row['initial_capital'],
                        risk_level=row['risk_level'],
                        sector=row['sector'],
                        status=row['status'],
                        created_at=row['created_at'].timestamp(),
                        updated_at=row['updated_at'].timestamp()
                    ) for row in rows
                ]
        except Exception as e:
            logger.error(f"Error retrieving user portfolios: {e}")
            return []
        