# source/sod/corporate_actions/adjustments.py
import logging
from typing import Dict, List, Any, Optional, Tuple
from datetime import date, datetime, timedelta
from decimal import Decimal
from enum import Enum

logger = logging.getLogger(__name__)

class AdjustmentType(Enum):
    PRICE = "price"
    QUANTITY = "quantity"
    CASH = "cash"
    SYMBOL_CHANGE = "symbol_change"

class AdjustmentStatus(Enum):
    PENDING = "pending"
    APPLIED = "applied"
    FAILED = "failed"
    REVERSED = "reversed"

class CorporateActionAdjustments:
    """Handles price and position adjustments - NO DATABASE ACCESS EVER"""
    
    def __init__(self, db_manager):
        self.db_manager = db_manager
        
    async def initialize(self):
        """Initialize adjustments processor"""
        # NO database access here - tables created by database manager only
        logger.info("⚖️ Corporate Action Adjustments initialized")
    
    # =================================================================
    # DIVIDEND ADJUSTMENTS - ALL THROUGH DATABASE MANAGER
    # =================================================================
    
    async def apply_dividend_adjustments(self, symbol: str, ex_date: date,
                                       dividend_amount: Decimal, currency: str = "USD") -> Dict[str, Any]:
        """Apply comprehensive dividend adjustments"""
        logger.info(f"💰 Applying dividend adjustments for {symbol}: ${dividend_amount}")
        
        try:
            results = {
                "symbol": symbol,
                "ex_date": ex_date.isoformat(),
                "dividend_amount": float(dividend_amount),
                "currency": currency,
                "position_adjustments": 0,
                "price_adjustments": 0,
                "total_dividend_paid": 0.0
            }
            
            # Apply dividend to positions through database manager ONLY
            position_result = await self._apply_dividend_to_positions(symbol, ex_date, dividend_amount, currency)
            results.update(position_result)
            
            # Apply price adjustments through database manager ONLY
            price_result = await self._adjust_historical_prices_dividend(symbol, ex_date, dividend_amount)
            results["price_adjustments"] = price_result["adjustments_made"]
            
            logger.info(f"✅ Dividend adjustments completed: {results}")
            return results
            
        except Exception as e:
            logger.error(f"❌ Failed to apply dividend adjustments for {symbol}: {e}", exc_info=True)
            raise
    
    async def _apply_dividend_to_positions(self, symbol: str, ex_date: date,
                                         dividend_amount: Decimal, currency: str) -> Dict[str, Any]:
        """Apply dividend payments - database manager ONLY"""
        # Get positions through database manager ONLY
        positions = await self.db_manager.corporate_actions.get_long_positions_for_symbol(symbol)
        
        positions_adjusted = 0
        total_cash_distributed = Decimal('0')
        
        for position in positions:
            account_id = position['account_id']
            quantity = Decimal(str(position['quantity']))
            
            dividend_payment = quantity * dividend_amount
            total_cash_distributed += dividend_payment
            
            # Record through database manager ONLY
            await self.db_manager.corporate_actions.record_position_audit(
                account_id=account_id,
                symbol=symbol,
                adjustment_date=ex_date,
                adjustment_type="DIVIDEND",
                cash_impact=dividend_payment,
                adjustment_reason=f"Dividend payment: ${dividend_amount} per share ({currency})"
            )
            
            positions_adjusted += 1
        
        return {
            "positions_adjusted": positions_adjusted,
            "total_dividend_paid": float(total_cash_distributed)
        }
    
    async def _adjust_historical_prices_dividend(self, symbol: str, ex_date: date,
                                               dividend_amount: Decimal) -> Dict[str, Any]:
        """Adjust historical prices - database manager ONLY"""
        # Get historical prices through database manager ONLY
        historical_prices = await self.db_manager.corporate_actions.get_historical_prices(symbol, ex_date)
        
        adjustments_made = 0
        
        for price_record in historical_prices:
            old_price = Decimal(str(price_record['price']))
            new_price = old_price - dividend_amount
            
            # Update through database manager ONLY
            price_updated = await self.db_manager.corporate_actions.update_historical_price(
                symbol, price_record['price_date'], new_price
            )
            
            if price_updated:
                # Record through database manager ONLY
                await self.db_manager.corporate_actions.record_price_adjustment_history(
                    symbol=symbol,
                    adjustment_date=ex_date,
                    adjustment_type='DIVIDEND',
                    old_price=old_price,
                    new_price=new_price,
                    adjustment_factor=Decimal('1.0'),
                    dividend_amount=dividend_amount,
                    adjustment_reason=f'Dividend adjustment: ${dividend_amount}'
                )
                
                adjustments_made += 1
                
                if adjustments_made >= 1000:
                    break
        
        return {"adjustments_made": adjustments_made}
    
    # =================================================================
    # STOCK SPLIT ADJUSTMENTS - ALL THROUGH DATABASE MANAGER
    # =================================================================
    
    async def apply_stock_split_adjustments(self, symbol: str, ex_date: date,
                                          split_ratio: Decimal) -> Dict[str, Any]:
        """Apply stock split adjustments"""
        logger.info(f"🔄 Applying stock split adjustments for {symbol}: {split_ratio}:1")
        
        try:
            results = {
                "symbol": symbol,
                "ex_date": ex_date.isoformat(),
                "split_ratio": float(split_ratio),
                "position_adjustments": 0,
                "price_adjustments": 0
            }
            
            # Apply through database manager ONLY
            position_result = await self._apply_split_to_positions(symbol, ex_date, split_ratio)
            results["position_adjustments"] = position_result["positions_adjusted"]
            
            price_result = await self._adjust_historical_prices_split(symbol, ex_date, split_ratio)
            results["price_adjustments"] = price_result["adjustments_made"]
            
            logger.info(f"✅ Stock split adjustments completed: {results}")
            return results
            
        except Exception as e:
            logger.error(f"❌ Failed to apply stock split adjustments for {symbol}: {e}", exc_info=True)
            raise
    
    async def _apply_split_to_positions(self, symbol: str, ex_date: date,
                                      split_ratio: Decimal) -> Dict[str, Any]:
        """Apply split to positions - database manager ONLY"""
        # Get positions through database manager ONLY
        positions = await self.db_manager.corporate_actions.get_positions_for_symbol(symbol)
        
        positions_adjusted = 0
        
        for position in positions:
            account_id = position['account_id']
            old_quantity = Decimal(str(position['quantity']))
            old_avg_cost = Decimal(str(position['avg_cost']))
            
            new_quantity = old_quantity * split_ratio
            new_avg_cost = old_avg_cost / split_ratio
            
            # Record through database manager ONLY
            await self.db_manager.corporate_actions.record_position_audit(
                account_id=account_id,
                symbol=symbol,
                adjustment_date=ex_date,
                adjustment_type="STOCK_SPLIT",
                old_quantity=old_quantity,
                new_quantity=new_quantity,
                old_avg_cost=old_avg_cost,
                new_avg_cost=new_avg_cost,
                adjustment_reason=f"Stock split {split_ratio}:1"
            )
            
            positions_adjusted += 1
        
        return {"positions_adjusted": positions_adjusted}
    
    async def _adjust_historical_prices_split(self, symbol: str, ex_date: date,
                                            split_ratio: Decimal) -> Dict[str, Any]:
        """Adjust prices for split - database manager ONLY"""
        adjustment_factor = Decimal('1') / split_ratio
        
        # Update through database manager ONLY
        adjustments_made = await self.db_manager.corporate_actions.bulk_update_historical_prices(
            symbol, ex_date, adjustment_factor
        )
        
        # Record through database manager ONLY
        if adjustments_made > 0:
            await self.db_manager.corporate_actions.record_price_adjustment_history(
                symbol=symbol,
                adjustment_date=ex_date,
                adjustment_type='STOCK_SPLIT',
                adjustment_factor=adjustment_factor,
                split_ratio=split_ratio,
                adjustment_reason=f'Stock split adjustment: {split_ratio}:1'
            )
        
        return {"adjustments_made": adjustments_made}
    
    # =================================================================
    # SPIN-OFF ADJUSTMENTS - ALL THROUGH DATABASE MANAGER
    # =================================================================
    
    async def apply_spinoff_adjustments(self, parent_symbol: str, ex_date: date,
                                      adjustment_factor: Decimal) -> Dict[str, Any]:
        """Apply spin-off adjustments"""
        logger.info(f"🔄 Applying spin-off adjustments for {parent_symbol}: factor {adjustment_factor}")
        
        try:
            # Adjust through database manager ONLY
            adjustments_made = await self.db_manager.corporate_actions.bulk_update_historical_prices(
                parent_symbol, ex_date, adjustment_factor
            )
            
            # Record through database manager ONLY
            if adjustments_made > 0:
                await self.db_manager.corporate_actions.record_price_adjustment_history(
                    symbol=parent_symbol,
                    adjustment_date=ex_date,
                    adjustment_type='SPINOFF',
                    adjustment_factor=adjustment_factor,
                    adjustment_reason=f'Spin-off price adjustment: {adjustment_factor}'
                )
            
            results = {
                "symbol": parent_symbol,
                "ex_date": ex_date.isoformat(),
                "adjustment_factor": float(adjustment_factor),
                "adjustments_made": adjustments_made
            }
            
            logger.info(f"✅ Spin-off adjustments completed: {results}")
            return results
            
        except Exception as e:
            logger.error(f"❌ Failed to apply spin-off adjustments for {parent_symbol}: {e}", exc_info=True)
            raise
    
    # =================================================================
    # REVERSAL OPERATIONS - ALL THROUGH DATABASE MANAGER
    # =================================================================
    
    async def reverse_adjustments(self, symbol: str, adjustment_date: date,
                                adjustment_type: str) -> Dict[str, Any]:
        """Reverse adjustments - database manager ONLY"""
        logger.info(f"🔄 Reversing {adjustment_type} adjustments for {symbol} on {adjustment_date}")
        
        try:
            results = {
                "symbol": symbol,
                "adjustment_date": adjustment_date.isoformat(),
                "adjustment_type": adjustment_type,
                "price_reversals": 0,
                "position_reversals": 0
            }
            
            # Get adjustments through database manager ONLY
            adjustments = await self.db_manager.corporate_actions.get_adjustments_for_reversal(
                symbol, adjustment_date, adjustment_type
            )
            
            # Reverse price adjustments
            for adjustment in adjustments["price_adjustments"]:
                if adjustment_type == 'DIVIDEND':
                    dividend_amount = Decimal(str(adjustment['dividend_amount']))
                    await self._reverse_dividend_price_adjustment(symbol, dividend_amount)
                    
                elif adjustment_type == 'STOCK_SPLIT':
                    adjustment_factor = Decimal(str(adjustment['adjustment_factor']))
                    reverse_factor = Decimal('1') / adjustment_factor
                    await self._reverse_split_price_adjustment(symbol, reverse_factor)
                
                results["price_reversals"] += 1
            
            # Mark as reversed through database manager ONLY
            price_adjustment_ids = [adj['adjustment_id'] for adj in adjustments["price_adjustments"]]
            if price_adjustment_ids:
                await self.db_manager.corporate_actions.mark_adjustments_as_reversed(
                    price_adjustment_ids, "price_adjustment_history"
                )
            
            position_adjustment_ids = [adj['audit_id'] for adj in adjustments["position_adjustments"]]
            if position_adjustment_ids:
                await self.db_manager.corporate_actions.mark_adjustments_as_reversed(
                    position_adjustment_ids, "position_adjustment_audit"
                )
                results["position_reversals"] = len(position_adjustment_ids)
            
            logger.info(f"✅ Adjustments reversed: {results}")
            return results
            
        except Exception as e:
            logger.error(f"❌ Failed to reverse adjustments: {e}", exc_info=True)
            raise
    
    async def _reverse_dividend_price_adjustment(self, symbol: str, dividend_amount: Decimal):
        """Reverse dividend adjustment - database manager ONLY"""
        # Approximate reversal through database manager ONLY
        await self.db_manager.corporate_actions.bulk_update_historical_prices(
            symbol, date.today(), Decimal('1.0') + (dividend_amount / Decimal('100'))
        )
    
    async def _reverse_split_price_adjustment(self, symbol: str, reverse_factor: Decimal):
        """Reverse split adjustment - database manager ONLY"""
        await self.db_manager.corporate_actions.bulk_update_historical_prices(
            symbol, date.today(), reverse_factor
        )
    
    # =================================================================
    # REPORTING AND ANALYSIS - ALL THROUGH DATABASE MANAGER
    # =================================================================
    
    async def get_adjustment_summary(self, symbol: str = None, 
                                    start_date: date = None, end_date: date = None) -> Dict[str, Any]:
        """Get summary through database manager ONLY"""
        return await self.db_manager.corporate_actions.get_adjustment_summary(
            symbol, start_date, end_date
        )
    
    async def validate_adjustments(self, symbol: str, adjustment_date: date) -> Dict[str, Any]:
        """Validate adjustments - database manager ONLY"""
        logger.info(f"🔍 Validating adjustments for {symbol} on {adjustment_date}")
        
        validation_results = {
            "symbol": symbol,
            "adjustment_date": adjustment_date.isoformat(),
            "validation_status": "PASSED",
            "issues": [],
            "checks_performed": {},
            "summary": {}
        }
        
        try:
            # Get adjustments through database manager ONLY
            price_adjustments = await self.db_manager.corporate_actions.get_price_adjustments_by_date(
                symbol, adjustment_date
            )
            
            position_adjustments = await self.db_manager.corporate_actions.get_position_adjustments_by_date(
                symbol, adjustment_date
            )
            
            validation_results["checks_performed"]["price_adjustments"] = len(price_adjustments)
            validation_results["checks_performed"]["position_adjustments"] = len(position_adjustments)
            
            # Validate calculations
            for price_adj in price_adjustments:
                if price_adj.get('old_price') and price_adj.get('new_price'):
                    old_price = Decimal(str(price_adj['old_price']))
                    new_price = Decimal(str(price_adj['new_price']))
                    expected_factor = price_adj.get('adjustment_factor', 1.0)
                    
                    if abs(float(new_price - (old_price * Decimal(str(expected_factor))))) > 0.001:
                        validation_results["issues"].append({
                            "type": "PRICE_CALCULATION_MISMATCH",
                            "adjustment_id": price_adj['adjustment_id'],
                            "details": f"Price calculation inconsistent"
                        })
                        validation_results["validation_status"] = "FAILED"
            
            # Check for orphaned adjustments through database manager ONLY
            orphaned_adjustments = await self.db_manager.corporate_actions.get_orphaned_adjustments(
                symbol, adjustment_date
            )
            
            if orphaned_adjustments:
                validation_results["issues"].append({
                    "type": "ORPHANED_ADJUSTMENTS",
                    "count": len(orphaned_adjustments),
                    "details": "Adjustments found without corresponding corporate actions"
                })
                validation_results["validation_status"] = "FAILED"
            
            validation_results["summary"] = {
                "total_price_adjustments": len(price_adjustments),
                "total_position_adjustments": len(position_adjustments),
                "issues_found": len(validation_results["issues"]),
                "validation_passed": validation_results["validation_status"] == "PASSED"
            }
            
            logger.info(f"✅ Validation completed: {validation_results['validation_status']}")
            return validation_results
            
        except Exception as e:
            logger.error(f"❌ Validation failed: {e}", exc_info=True)
            validation_results["validation_status"] = "ERROR"
            validation_results["issues"].append({
                "type": "VALIDATION_ERROR",
                "details": str(e)
            })
            return validation_results
    
    async def generate_adjustment_report(self, symbol: str = None, 
                                        start_date: date = None, end_date: date = None) -> Dict[str, Any]:
        """Generate report - database manager ONLY"""
        logger.info(f"📊 Generating adjustment report for {symbol or 'all symbols'}")
        
        try:
            report = {
                "report_generated_at": datetime.utcnow().isoformat(),
                "filter_criteria": {
                    "symbol": symbol,
                    "start_date": start_date.isoformat() if start_date else None,
                    "end_date": end_date.isoformat() if end_date else None
                },
                "summary": await self.get_adjustment_summary(symbol, start_date, end_date),
                "detailed_adjustments": {},
                "recommendations": []
            }
            
            # Get detailed data through database manager ONLY
            detailed_price = await self.db_manager.corporate_actions.get_detailed_price_adjustments(
                symbol, start_date, end_date
            )
            
            detailed_position = await self.db_manager.corporate_actions.get_detailed_position_adjustments(
                symbol, start_date, end_date
            )
            
            report["detailed_adjustments"] = {
                "price_adjustments": detailed_price,
                "position_adjustments": detailed_position
            }
            
            # Generate recommendations
            if report["summary"]["price_adjustments"]:
                total_price_adjustments = sum(adj["count"] for adj in report["summary"]["price_adjustments"])
                if total_price_adjustments > 100:
                    report["recommendations"].append({
                        "type": "HIGH_VOLUME_ADJUSTMENTS",
                        "message": f"High volume of adjustments ({total_price_adjustments}). Review processes."
                    })
            
            logger.info(f"✅ Adjustment report generated successfully")
            return report
            
        except Exception as e:
            logger.error(f"❌ Failed to generate adjustment report: {e}", exc_info=True)
            raise
    
    # =================================================================
    # UTILITY METHODS - ALL THROUGH DATABASE MANAGER
    # =================================================================
    
    async def cleanup_old_adjustments(self, cutoff_date: date) -> Dict[str, Any]:
        """Cleanup through database manager ONLY"""
        logger.info(f"🧹 Cleaning up adjustment records older than {cutoff_date}")
        
        try:
            # Cleanup through database manager ONLY
            cleanup_summary = await self.db_manager.corporate_actions.cleanup_old_adjustment_records(
                cutoff_date
            )
            
            logger.info(f"✅ Cleanup completed: {cleanup_summary}")
            return cleanup_summary
            
        except Exception as e:
            logger.error(f"❌ Cleanup failed: {e}", exc_info=True)
            raise
    
    async def get_adjustment_statistics(self, days_back: int = 30) -> Dict[str, Any]:
        """Get statistics through database manager ONLY"""
        end_date = date.today()
        start_date = end_date - timedelta(days=days_back)
        
        try:
            # Get statistics through database manager ONLY
            stats = await self.db_manager.corporate_actions.get_adjustment_statistics(
                start_date, end_date
            )
            
            return {
                "period": {
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat(),
                    "days": days_back
                },
                "statistics": stats,
                "generated_at": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"❌ Failed to generate statistics: {e}", exc_info=True)
            raise


# =============================================================================
# UTILITY FUNCTIONS - ALL THROUGH DATABASE MANAGER
# =============================================================================

async def validate_adjustment_consistency(adjustments_processor: CorporateActionAdjustments, symbol: str, start_date: date, end_date: date) -> Dict[str, Any]:
    """Utility function - database manager ONLY"""
    validation_results = {
        "symbol": symbol,
        "date_range": f"{start_date} to {end_date}",
        "overall_status": "PASSED",
        "daily_validations": [],
        "summary": {
            "total_days_checked": 0,
            "days_with_issues": 0,
            "total_issues": 0
        }
    }
    
    current_date = start_date
    while current_date <= end_date:
        # Validate through the adjustments processor (which uses database manager ONLY)
        daily_validation = await adjustments_processor.validate_adjustments(symbol, current_date)
        
        validation_results["daily_validations"].append({
            "date": current_date.isoformat(),
            "status": daily_validation["validation_status"],
            "issues_count": len(daily_validation["issues"]),
            "issues": daily_validation["issues"]
        })
        
        if daily_validation["validation_status"] != "PASSED":
            validation_results["overall_status"] = "FAILED"
            validation_results["summary"]["days_with_issues"] += 1
            validation_results["summary"]["total_issues"] += len(daily_validation["issues"])
        
        validation_results["summary"]["total_days_checked"] += 1
        current_date = current_date + timedelta(days=1)
    
    return validation_results