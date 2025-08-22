# source/engines/v01/engine.py
from typing import Dict, List, Any, Tuple
import traceback
import numpy as np
from scipy.optimize import minimize

from source.engines.base_engine import BaseEngine


class ENGINE_v01(BaseEngine):
    """
    Portfolio optimization engine that properly uses existing managers.

    Process:
    1. Get book's base currency from database
    2. Get current portfolio from portfolio manager in book_context (converted to base currency)
    3. Get target portfolio from convictions (engine-specific logic)
    4. Get exchange parameters using db_manager.load_exchange_parameters()
    5. Get book parameters using db_manager.load_book_operational_parameters()
    6. Solve optimization problem in base currency notionals
    7. Generate orders from solution (converting back to symbol quantities using latest prices)
    """

    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(engine_id=1, config=config)

    def validate_conviction(self, conviction: Dict[str, Any]) -> str:
        """Validate conviction for basic engine."""
        required_fields = ['instrument_id', 'side', 'quantity']

        for field in required_fields:
            if field not in conviction or conviction[field] is None:
                return f"Missing required field: {field}"

        # Validate side
        if conviction['side'] not in ['BUY', 'SELL']:
            return f"Invalid side: {conviction['side']}"

        # Validate quantity
        try:
            quantity = float(conviction['quantity'])
            if quantity <= 0:
                return f"Invalid quantity: {quantity}"
        except (ValueError, TypeError):
            return f"Invalid quantity: {conviction['quantity']}"

        return ""

    async def convert_convictions_to_orders(self,
                                            book_id: str,
                                            convictions: List[Dict[str, Any]],
                                            book_context: Any) -> List[Dict[str, Any]]:
        """Convert convictions to orders using portfolio optimization."""
        return await self._async_portfolio_optimization(book_id, convictions, book_context)

    async def _async_portfolio_optimization(self,
                                            book_id: str,
                                            convictions: List[Dict[str, Any]],
                                            book_context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Main optimization workflow using existing managers."""

        try:
            # Step 1: Get current portfolio from book_context portfolio manager (in base currency)
            current_portfolio = self.get_current_notional_portfolio_from_manager(book_context)
            self.logger.info(f"Current portfolio for {book_id}: {len(current_portfolio)}")

            # Step 2: Get target portfolio from convictions (ENGINE SPECIFIC) (in base currency)
            target_portfolio = self._get_target_notional_portfolio_from_convictions(
                current_portfolio, convictions, book_context
            )
            self.logger.info(f"Target portfolio from convictions: {len(target_portfolio)}")

            # Step 5: Solve optimization problem in base currency
            optimal_portfolio, optimization_result = self._solve_optimization_problem(
                book_context=book_context,
                current_portfolio=current_portfolio,
                target_portfolio=target_portfolio
            )

            print("OK NOW CREATE THE ORDER")

            # Step 6: Generate orders from solution (converting back to symbol quantities)
            orders = self._generate_orders_from_notional_solution(
                current_portfolio=current_portfolio,
                optimal_portfolio=optimal_portfolio,
                book_context=book_context,
                convictions=convictions
            )

            print(f"ORDER: {orders}")

            self.logger.info(f"Generated {len(orders)} orders from optimization for {book_id}")
            return orders

        except Exception as e:
            self.logger.error(f"Error in portfolio optimization for book {book_id}: {e}")
            return []

    def _get_target_notional_portfolio_from_convictions(self,
                                                        current_portfolio: Dict[str, float],
                                                        convictions: List[Dict[str, Any]],
                                                        book_context: Any) -> Dict[str, float]:
        """
        ENGINE SPECIFIC: Convert convictions to target portfolio notionals in base currency.
        This is specific to ENGINE_v01 logic.
        """
        base_currency = book_context.base_currency

        target_portfolio = {}


        for conviction in convictions:
            print(f"CONVICTION: {conviction}")

            symbol = conviction.get('instrument_id')
            if not symbol:
                continue

            try:
                current_notional = current_portfolio.get(symbol, 0)

                side = conviction.get('side', 'BUY')
                quantity = float(conviction.get('quantity', 0))

                # Get latest price for the symbol
                latest_price = self.utils.get_symbol_latest_price(symbol, book_context)
                if latest_price is None:
                    self.logger.warning(f"No price available for {symbol}, skipping")
                    continue

                print(f"LATEST PRICE: {latest_price}")

                # Calculate notional value in symbol's native currency
                delta_notional_value = quantity * float(latest_price)

                # Get symbol currency and convert to base currency
                symbol_currency = self.utils.get_symbol_currency(symbol, book_context)
                delta_notional_value = self.utils.convert_to_base_currency(
                    delta_notional_value, symbol_currency, base_currency, book_context
                )

                # Apply side (BUY = positive, SELL = negative)
                if side == 'SELL':
                    delta_notional_value = -delta_notional_value

                print(f"NOTIONAL VALUE: {current_notional} > {delta_notional_value}")

                target_portfolio[symbol] = current_notional + delta_notional_value

            except Exception as e:
                self.logger.error(f"Error processing conviction for {symbol}: {e}")
                continue

        return target_portfolio

    def _solve_optimization_problem(self,
                                    book_context: Any,
                                    current_portfolio: Dict[str, float],
                                    target_portfolio: Dict[str, float]
                                    ) -> Tuple[Dict[str, float], Dict]:
        """
        Solve portfolio optimization problem using a common framework.

        Framework:
        1. Set up decision variables (positions for each symbol)
        2. Define objective function (minimize deviation from target)
        3. Add constraints (book min/max limits, budget constraint)
        4. Solve using optimization solver
        5. Return optimal portfolio and result metadata
        """
        base_currency = book_context.base_currency
        self.logger.info(f"Setting up optimization problem in {base_currency}")

        print(f"CURRENT: {current_portfolio}")
        print(f"TARGET: {target_portfolio}")

        try:

            print("1")

            # ==========================================
            # STEP 1: SETUP DECISION VARIABLES
            # ==========================================

            # Get all unique symbols from current and target portfolios
            all_symbols = sorted(set(list(current_portfolio.keys()) + list(target_portfolio.keys())))
            n_symbols = len(all_symbols)

            if n_symbols == 0:
                self.logger.warning("No symbols to optimize")
                return {}, {'status': 'no_symbols', 'message': 'No symbols provided'}

            print("2")

            self.logger.info(f"Optimizing {n_symbols} symbols: {all_symbols}")

            # Current positions vector
            current_positions = np.array([current_portfolio.get(symbol, 0.0) for symbol in all_symbols])

            # Target positions vector
            target_positions = np.array([target_portfolio.get(symbol, 0.0) for symbol in all_symbols])

            self.logger.info(f"Current total: {np.sum(current_positions):,.2f} {base_currency}")
            self.logger.info(f"Target total: {np.sum(target_positions):,.2f} {base_currency}")

            print(f"3: CURRENT: {current_positions}")
            print(f"3: TARGET: {target_positions}")

            # ==========================================
            # STEP 2: DEFINE OBJECTIVE FUNCTION
            # ==========================================

            def objective_function(x):
                """
                Minimize squared deviation from target positions.
                x: vector of optimal positions for each symbol
                """
                deviation = x - target_positions
                return np.sum(deviation ** 2)

            # ==========================================
            # STEP 3: SETUP CONSTRAINTS
            # ==========================================

            constraints = []
            bounds = []

            # Get NAV from account manager (this is your total budget)
            account_manager = book_context.app_state.account_manager
            if hasattr(account_manager, 'get_nav') or hasattr(account_manager, 'get_total_value'):
                total_budget = account_manager.get_nav()  # or get_total_value()
            else:
                total_budget = book_context.initial_nav

            print(f"4: TOTAL: {total_budget}")

            # FIXED: Budget constraint should be "don't exceed budget" not "use entire budget"
            def budget_constraint(x):
                # Total portfolio value should not exceed available budget
                # This is an inequality constraint: sum(x) <= total_budget
                return float(total_budget) - np.sum(x)  # Must be >= 0

            constraints.append({
                'type': 'ineq',  # FIXED: Changed from 'eq' to 'ineq'
                'fun': budget_constraint
            })

            print(f"5: CONSTRAINTS: Budget <= {total_budget}")

            self.logger.info(f"Budget constraint: total = {total_budget:,.2f} {base_currency}")

            print(f"5: BASE CURRENCY: {base_currency}")

            # B) book position limits (min/max constraints per symbol)
            for i, symbol in enumerate(all_symbols):
                symbol_min = None
                symbol_max = None

                # Check book parameters for symbol-specific limits
                """
                if book_params:
                    position_limits = book_params.get('position_limits', {})
                    if symbol in position_limits:
                        symbol_min = position_limits[symbol].get('min_position_size_pct')
                        symbol_max = position_limits[symbol].get('max_position_size_pct')

                    # Global limits as fallback
                    if symbol_min is None:
                        symbol_min = book_params.get('min_position_size_pct')
                    if symbol_max is None:
                        symbol_max = book_params.get('max_position_size_pct')
                """

                # Set bounds for this symbol
                lower_bound = symbol_min if symbol_min is not None else -float(total_budget)# np.inf
                upper_bound = symbol_max if symbol_max is not None else float(total_budget)# np.inf

                bounds.append((lower_bound, upper_bound))

                if symbol_min is not None or symbol_max is not None:
                    self.logger.debug(f"Position limits for {symbol}: [{lower_bound}, {upper_bound}]")

            print(f"6: BOUNDS: {bounds}")

            # C) Additional constraints can be added here
            # - Sector limits
            # - Risk limits
            # - Turnover limits
            # - etc.

            # ==========================================
            # STEP 4: SOLVE OPTIMIZATION PROBLEM
            # ==========================================

            # Initial guess: start from current positions
            x0 = current_positions.copy()

            self.logger.info("Solving optimization problem...")
            self.logger.info(f"Solver: scipy.optimize.minimize (SLSQP)")
            self.logger.info(f"Variables: {n_symbols}")
            self.logger.info(f"Constraints: {len(constraints)}")

            # Solve the optimization problem
            result = minimize(
                fun=objective_function,
                x0=x0,
                method='SLSQP',  # Sequential Least Squares Programming
                bounds=bounds,
                constraints=constraints,
                options={
                    'ftol': 1e-8,
                    'disp': False,
                    'maxiter': 1000
                }
            )

            print(f"7: {result}")

            # ==========================================
            # STEP 5: PROCESS RESULTS
            # ==========================================

            if result.success:
                # Extract optimal positions
                optimal_positions = result.x

                # Convert back to dictionary
                optimal_portfolio = {}
                for i, symbol in enumerate(all_symbols):
                    position = optimal_positions[i]
                    # Only include non-zero positions (with small threshold)
                    if abs(position) > 0.01:
                        optimal_portfolio[symbol] = float(position)

                print(f"8: FINAL: {optimal_portfolio}")

                # Calculate metrics
                total_deviation = np.sum(np.abs(optimal_positions - target_positions))
                max_deviation = np.max(np.abs(optimal_positions - target_positions))

                optimization_result = {
                    'status': 'optimal',
                    'solver': 'scipy.SLSQP',
                    'objective_value': float(result.fun),
                    'total_deviation': float(total_deviation),
                    'max_deviation': float(max_deviation),
                    'base_currency': base_currency,
                    'symbols_optimized': len(optimal_portfolio),
                    'iterations': result.nit,
                    'function_evaluations': result.nfev,
                    'message': result.message,
                    'total_budget': float(total_budget),
                    'constraints_satisfied': all(
                        abs(c['fun'](optimal_positions)) < 1e-6 for c in constraints if 'fun' in c)
                }

                print(f"9: RESULT: {optimization_result}")

                self.logger.info(f"✅ Optimization successful!")
                self.logger.info(f"   Objective value: {result.fun:.6f}")
                self.logger.info(f"   Total deviation: {total_deviation:.2f} {base_currency}")
                self.logger.info(f"   Positions: {len(optimal_portfolio)} symbols")
                self.logger.info(f"   Iterations: {result.nit}")

                return optimal_portfolio, optimization_result

            else:
                # Optimization failed
                self.logger.error(f"❌ Optimization failed: {result.message}")

                # Fallback: return target portfolio (or current if target is empty)
                fallback_portfolio = target_portfolio if target_portfolio else current_portfolio

                print("10")

                optimization_result = {
                    'status': 'failed',
                    'solver': 'scipy.SLSQP',
                    'error': result.message,
                    'base_currency': base_currency,
                    'fallback_used': True,
                    'symbols_in_fallback': len(fallback_portfolio),
                    'iterations': result.nit if hasattr(result, 'nit') else 0
                }

                return fallback_portfolio, optimization_result

        except ImportError as e:
            self.logger.error(f"❌ Optimization solver not available: {e}")
            self.logger.info("💡 Install scipy: pip install scipy")

            # Fallback to simple target following
            return self._simple_target_following_fallback(
                current_portfolio, target_portfolio, base_currency
            )

        except Exception as e:
            self.logger.error(f"❌ Error in optimization: {e}")
            self.logger.error(f"Full traceback: {traceback.format_exc()}")

            # Fallback to simple target following
            return self._simple_target_following_fallback(
                current_portfolio, target_portfolio, base_currency
            )

    def _simple_target_following_fallback(self,
                                          current_portfolio: Dict[str, float],
                                          target_portfolio: Dict[str, float],
                                          base_currency: str) -> Tuple[Dict[str, float], Dict]:
        """
        Fallback method when optimization solver is not available.
        Simply moves towards target positions without constraints.
        """
        self.logger.info("Using simple target following fallback")

        # Get all symbols
        all_symbols = set(list(current_portfolio.keys()) + list(target_portfolio.keys()))

        optimal_portfolio = {}
        for symbol in all_symbols:
            target_position = target_portfolio.get(symbol, 0.0)
            if abs(target_position) > 0.01:  # Only include significant positions
                optimal_portfolio[symbol] = target_position

        optimization_result = {
            'status': 'fallback',
            'method': 'simple_target_following',
            'base_currency': base_currency,
            'symbols_optimized': len(optimal_portfolio),
            'message': 'Used simple fallback due to solver unavailability'
        }

        return optimal_portfolio, optimization_result