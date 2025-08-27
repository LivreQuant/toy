# source/sod/corporate_actions/ca_processor.py
import logging
from typing import Dict, List, Any, Optional
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
import asyncio

logger = logging.getLogger(__name__)

class ActionType(Enum):
    DIVIDEND = "dividend"
    STOCK_SPLIT = "stock_split"
    STOCK_DIVIDEND = "stock_dividend"
    SPIN_OFF = "spin_off"
    MERGER = "merger"
    RIGHTS_OFFERING = "rights_offering"
    SPECIAL_DIVIDEND = "special_dividend"

class ActionStatus(Enum):
    PENDING = "pending"
    PROCESSED = "processed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class CorporateActionsProcessor:
    """Processes corporate actions and applies adjustments - NO DATABASE ACCESS"""
    
    def __init__(self, db_manager):
        self.db_manager = db_manager
        
    async def initialize(self):
        """Initialize corporate actions processor"""
        # Initialize tables through the database manager ONLY
        if hasattr(self.db_manager, 'corporate_actions'):
            await self.db_manager.corporate_actions.initialize_tables()
        
        logger.info("🏢 Corporate Actions Processor initialized")
    
    async def process_pending_actions(self, processing_date: date = None) -> Dict[str, Any]:
        """Process all pending corporate actions for the given date"""
        if processing_date is None:
            processing_date = date.today()
        
        logger.info(f"🏢 Processing corporate actions for {processing_date}")
        
        try:
            # Get all pending actions through database manager ONLY
            pending_actions = await self.db_manager.corporate_actions.get_pending_actions(processing_date)
            
            if not pending_actions:
                logger.info("No pending corporate actions to process")
                return {
                    "total_actions": 0,
                    "processed_actions": 0,
                    "failed_actions": 0,
                    "by_type": {}
                }
            
            logger.info(f"Found {len(pending_actions)} pending corporate actions")
            
            results = {
                "total_actions": len(pending_actions),
                "processed_actions": 0,
                "failed_actions": 0,
                "by_type": {},
                "processing_details": []
            }
            
            # Process each action
            for action in pending_actions:
                try:
                    action_result = await self._process_single_action(action, processing_date)
                    
                    if action_result["success"]:
                        results["processed_actions"] += 1
                    else:
                        results["failed_actions"] += 1
                    
                    # Track by type
                    action_type = action["action_type"]
                    if action_type not in results["by_type"]:
                        results["by_type"][action_type] = {"processed": 0, "failed": 0}
                    
                    if action_result["success"]:
                        results["by_type"][action_type]["processed"] += 1
                    else:
                        results["by_type"][action_type]["failed"] += 1
                    
                    results["processing_details"].append({
                        "action_id": action["action_id"],
                        "symbol": action["symbol"],
                        "action_type": action["action_type"],
                        "success": action_result["success"],
                        "details": action_result.get("details", {}),
                        "error": action_result.get("error")
                    })
                    
                except Exception as e:
                    logger.error(f"❌ Failed to process action {action['action_id']}: {e}", exc_info=True)
                    results["failed_actions"] += 1
                    
                    # Mark action as failed through database manager
                    await self.db_manager.corporate_actions.update_action_status(
                        action["action_id"], "FAILED", str(e)
                    )
            
            logger.info(f"✅ Processed {results['processed_actions']}/{results['total_actions']} corporate actions")
            return results
            
        except Exception as e:
            logger.error(f"❌ Corporate actions processing failed: {e}", exc_info=True)
            raise
    
    async def _process_single_action(self, action: Dict[str, Any], processing_date: date) -> Dict[str, Any]:
        """Process a single corporate action"""
        action_id = action["action_id"]
        symbol = action["symbol"]
        action_type = action["action_type"]
        action_details = action["action_details"]
        
        logger.info(f"🔄 Processing {action_type} for {symbol} (ID: {action_id})")
        
        try:
            # Route to appropriate handler based on action type
            if action_type == ActionType.DIVIDEND.value:
                result = await self._process_dividend(action_id, symbol, processing_date, action_details)
            elif action_type == ActionType.STOCK_SPLIT.value:
                result = await self._process_stock_split(action_id, symbol, processing_date, action_details)
            elif action_type == ActionType.STOCK_DIVIDEND.value:
                result = await self._process_stock_dividend(action_id, symbol, processing_date, action_details)
            elif action_type == ActionType.SPIN_OFF.value:
                result = await self._process_spinoff(action_id, symbol, processing_date, action_details)
            elif action_type == ActionType.MERGER.value:
                result = await self._process_merger(action_id, symbol, processing_date, action_details)
            else:
                raise ValueError(f"Unsupported action type: {action_type}")
            
            # Mark action as processed if successful - through database manager ONLY
            if result.get("success", False):
                await self.db_manager.corporate_actions.update_action_status(action_id, "PROCESSED")
                logger.info(f"✅ {action_type} processed successfully for {symbol}")
            else:
                await self.db_manager.corporate_actions.update_action_status(
                    action_id, "FAILED", result.get("error", "Unknown error")
                )
                logger.error(f"❌ {action_type} processing failed for {symbol}: {result.get('error')}")
            
            return result
            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"❌ Failed to process {action_type} for {symbol}: {e}", exc_info=True)
            
            # Mark action as failed through database manager ONLY
            await self.db_manager.corporate_actions.update_action_status(action_id, "FAILED", error_msg)
            
            return {"success": False, "error": error_msg}
    
    async def _process_dividend(self, action_id: str, symbol: str, processing_date: date,
                              details: Dict[str, Any]) -> Dict[str, Any]:
        """Process dividend payment"""
        try:
            dividend_amount = Decimal(str(details.get("dividend_amount", "0")))
            currency = details.get("currency", "USD")
            
            # Get all long positions through database manager ONLY
            positions = await self.db_manager.corporate_actions.get_long_positions_for_symbol(symbol)
            
            total_dividend_paid = Decimal("0")
            positions_affected = 0
            
            for position in positions:
                account_id = position["account_id"]
                quantity = Decimal(str(position["quantity"]))
                
                # Calculate dividend payment
                dividend_payment = quantity * dividend_amount
                total_dividend_paid += dividend_payment
                positions_affected += 1
                
                # Record the dividend adjustment through database manager ONLY
                await self.db_manager.corporate_actions.record_position_audit(
                    account_id=account_id,
                    symbol=symbol,
                    adjustment_date=processing_date,
                    adjustment_type="DIVIDEND",
                    cash_impact=dividend_payment,
                    corporate_action_id=action_id,
                    adjustment_reason=f"Dividend payment: ${dividend_amount} per share"
                )
            
            # Record price adjustment through database manager ONLY
            await self.db_manager.corporate_actions.record_price_adjustment(
                action_id=action_id,
                symbol=symbol,
                adjustment_date=processing_date,
                adjustment_factor=Decimal("1.0"),
                dividend_amount=dividend_amount,
                adjustment_type="DIVIDEND"
            )
            
            return {
                "success": True,
                "details": {
                    "dividend_amount": float(dividend_amount),
                    "total_dividend_paid": float(total_dividend_paid),
                    "positions_affected": positions_affected,
                    "currency": currency
                }
            }
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _process_stock_split(self, action_id: str, symbol: str, processing_date: date,
                                 details: Dict[str, Any]) -> Dict[str, Any]:
        """Process stock split"""
        try:
            split_ratio = Decimal(str(details.get("split_ratio", "2.0")))
            
            # Get all positions through database manager ONLY
            positions = await self.db_manager.corporate_actions.get_positions_for_symbol(symbol)
            
            positions_adjusted = 0
            
            for position in positions:
                account_id = position["account_id"]
                old_quantity = Decimal(str(position["quantity"]))
                old_avg_cost = Decimal(str(position["avg_cost"]))
                
                new_quantity = old_quantity * split_ratio
                new_avg_cost = old_avg_cost / split_ratio
                
                # Record position adjustment through database manager ONLY
                await self.db_manager.corporate_actions.record_position_adjustment(
                    action_id=action_id,
                    account_id=account_id,
                    symbol=symbol,
                    adjustment_date=processing_date,
                    old_quantity=old_quantity,
                    new_quantity=new_quantity,
                    old_price=old_avg_cost,
                    new_price=new_avg_cost,
                    adjustment_reason=f"Stock split {split_ratio}:1"
                )
                
                # Record audit through database manager ONLY
                await self.db_manager.corporate_actions.record_position_audit(
                    account_id=account_id,
                    symbol=symbol,
                    adjustment_date=processing_date,
                    adjustment_type="STOCK_SPLIT",
                    old_quantity=old_quantity,
                    new_quantity=new_quantity,
                    old_avg_cost=old_avg_cost,
                    new_avg_cost=new_avg_cost,
                    corporate_action_id=action_id,
                    adjustment_reason=f"Stock split {split_ratio}:1"
                )
                
                positions_adjusted += 1
            
            # Update historical prices through database manager ONLY
            adjustment_factor = Decimal('1') / split_ratio
            price_adjustments = await self.db_manager.corporate_actions.bulk_update_historical_prices(
                symbol, processing_date, adjustment_factor
            )
            
            # Record price adjustment through database manager ONLY
            await self.db_manager.corporate_actions.record_price_adjustment(
                action_id=action_id,
                symbol=symbol,
                adjustment_date=processing_date,
                adjustment_factor=adjustment_factor,
                adjustment_type="STOCK_SPLIT"
            )
            
            return {
                "success": True,
                "details": {
                    "split_ratio": float(split_ratio),
                    "positions_adjusted": positions_adjusted,
                    "price_adjustments_made": price_adjustments,
                    "adjustment_factor": float(adjustment_factor)
                }
            }
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _process_stock_dividend(self, action_id: str, symbol: str, processing_date: date,
                                    details: Dict[str, Any]) -> Dict[str, Any]:
        """Process stock dividend"""
        try:
            dividend_ratio = Decimal(str(details.get("dividend_ratio", "0.05")))
            
            # Get positions through database manager ONLY
            positions = await self.db_manager.corporate_actions.get_positions_for_symbol(symbol)
            
            positions_adjusted = 0
            total_shares_distributed = Decimal("0")
            
            for position in positions:
                account_id = position["account_id"]
                old_quantity = Decimal(str(position["quantity"]))
                old_avg_cost = Decimal(str(position["avg_cost"]))
                
                additional_shares = old_quantity * dividend_ratio
                new_quantity = old_quantity + additional_shares
                new_avg_cost = old_avg_cost * old_quantity / new_quantity
                total_shares_distributed += additional_shares
                
                # Record through database manager ONLY
                await self.db_manager.corporate_actions.record_position_adjustment(
                    action_id=action_id,
                    account_id=account_id,
                    symbol=symbol,
                    adjustment_date=processing_date,
                    old_quantity=old_quantity,
                    new_quantity=new_quantity,
                    old_price=old_avg_cost,
                    new_price=new_avg_cost,
                    adjustment_reason=f"Stock dividend {dividend_ratio * 100}%"
                )
                
                positions_adjusted += 1
            
            return {
                "success": True,
                "details": {
                    "dividend_ratio": float(dividend_ratio),
                    "positions_adjusted": positions_adjusted,
                    "total_shares_distributed": float(total_shares_distributed)
                }
            }
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _process_spinoff(self, action_id: str, symbol: str, processing_date: date,
                             details: Dict[str, Any]) -> Dict[str, Any]:
        """Process spin-off"""
        try:
            new_symbol = details.get("new_symbol")
            distribution_ratio = Decimal(str(details.get("distribution_ratio", "1.0")))
            new_security_price = Decimal(str(details.get("new_security_price", "0")))
            
            if not new_symbol:
                raise ValueError("new_symbol is required for spin-off")
            
            # Get positions through database manager ONLY
            positions = await self.db_manager.corporate_actions.get_long_positions_for_symbol(symbol)
            
            positions_affected = 0
            total_new_shares = Decimal("0")
            
            for position in positions:
                account_id = position["account_id"]
                old_quantity = Decimal(str(position["quantity"]))
                
                new_shares = old_quantity * distribution_ratio
                total_new_shares += new_shares
                
                # Record through database manager ONLY
                await self.db_manager.corporate_actions.record_position_adjustment(
                    action_id=action_id,
                    account_id=account_id,
                    symbol=new_symbol,
                    adjustment_date=processing_date,
                    old_quantity=Decimal("0"),
                    new_quantity=new_shares,
                    new_price=new_security_price,
                    adjustment_reason=f"Spin-off from {symbol}: {distribution_ratio} shares per original share"
                )
                
                positions_affected += 1
            
            return {
                "success": True,
                "details": {
                    "original_symbol": symbol,
                    "new_symbol": new_symbol,
                    "distribution_ratio": float(distribution_ratio),
                    "positions_affected": positions_affected,
                    "total_new_shares_distributed": float(total_new_shares)
                }
            }
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _process_merger(self, action_id: str, symbol: str, processing_date: date,
                            details: Dict[str, Any]) -> Dict[str, Any]:
        """Process merger"""
        try:
            acquiring_symbol = details.get("acquiring_symbol")
            cash_amount = Decimal(str(details.get("cash_amount", "0")))
            stock_ratio = Decimal(str(details.get("stock_ratio", "0")))
            
            # Get positions through database manager ONLY
            positions = await self.db_manager.corporate_actions.get_positions_for_symbol(symbol)
            
            positions_affected = 0
            total_cash_distributed = Decimal("0")
            total_new_shares = Decimal("0")
            
            for position in positions:
                account_id = position["account_id"]
                old_quantity = Decimal(str(position["quantity"]))
                
                if old_quantity > 0:
                    total_cash = old_quantity * cash_amount if cash_amount > 0 else Decimal("0")
                    new_shares = old_quantity * stock_ratio if stock_ratio > 0 and acquiring_symbol else Decimal("0")
                    
                    total_cash_distributed += total_cash
                    total_new_shares += new_shares
                    
                    # Record through database manager ONLY
                    await self.db_manager.corporate_actions.record_position_adjustment(
                        action_id=action_id,
                        account_id=account_id,
                        symbol=symbol,
                        adjustment_date=processing_date,
                        old_quantity=old_quantity,
                        new_quantity=Decimal("0"),
                        cash_adjustment=total_cash,
                        adjustment_reason=f"Merger: {symbol} acquired"
                    )
                    
                    positions_affected += 1
            
            return {
                "success": True,
                "details": {
                    "target_symbol": symbol,
                    "acquiring_symbol": acquiring_symbol,
                    "positions_affected": positions_affected,
                    "total_cash_distributed": float(total_cash_distributed),
                    "total_new_shares_distributed": float(total_new_shares)
                }
            }
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    # =================================================================
    # UTILITY METHODS - ALL GO THROUGH DATABASE MANAGER
    # =================================================================
    
    async def add_corporate_action(self, symbol: str, action_type: ActionType,
                                 announcement_date: date, ex_date: date,
                                 action_details: Dict[str, Any],
                                 record_date: date = None, payment_date: date = None,
                                 effective_date: date = None) -> str:
        """Add a new corporate action through database manager ONLY"""
        return await self.db_manager.corporate_actions.create_corporate_action(
            symbol=symbol,
            action_type=action_type.value,
            announcement_date=announcement_date,
            ex_date=ex_date,
            action_details=action_details,
            record_date=record_date,
            payment_date=payment_date,
            effective_date=effective_date
        )
    
    async def get_pending_actions_summary(self) -> Dict[str, Any]:
        """Get summary through database manager ONLY"""
        return await self.db_manager.corporate_actions.get_pending_actions_summary()
    
    async def get_corporate_action_status(self, action_id: str) -> Optional[Dict[str, Any]]:
        """Get status through database manager ONLY"""
        return await self.db_manager.corporate_actions.get_corporate_action(action_id)
    
    async def cancel_corporate_action(self, action_id: str, reason: str = None) -> bool:
        """Cancel through database manager ONLY"""
        try:
            await self.db_manager.corporate_actions.update_action_status(
                action_id, "CANCELLED", reason or "Cancelled by system"
            )
            logger.info(f"📋 Corporate action {action_id} cancelled: {reason}")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to cancel corporate action {action_id}: {e}")
            return False