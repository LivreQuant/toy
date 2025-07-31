# source/conviction_engine/alpha_engines/target_weight/engine.py
from typing import Dict, List, Optional
from datetime import datetime
import logging

from .config_loader import ConfigLoader
from .alpha_processor import AlphaProcessor, TargetWeightSignal
from .constraint_manager import ConstraintManager
from .risk_manager import RiskManager
from .solver import TargetWeightSolver
from .order_generator import OrderGenerator


class TargetWeightEngine:
    """Configuration-driven target weight engine"""

    def __init__(self, config_path: Optional[str] = None, config_overrides: Optional[Dict] = None):
        # Load configuration
        self.config_loader = ConfigLoader(config_path)
        self.config = self.config_loader.load_config()

        # Apply any overrides
        if config_overrides:
            self.config = ConfigLoader.override_config(self.config, config_overrides)

        # Setup logging
        self._setup_logging()

        self.logger.info(f"Initializing {self.config['engine']['name']} v{self.config['engine']['version']}")

        # Initialize components with configuration
        self.alpha_processor = AlphaProcessor(self.config)
        self.constraint_manager = ConstraintManager(self.config)
        self.risk_manager = RiskManager(self.config)
        self.solver = TargetWeightSolver(self.config)
        self.order_generator = OrderGenerator(self.config)

        self.logger.info("Target weight engine initialized successfully")

    def _setup_logging(self):
        """Setup logging from configuration"""

        logging_config = self.config.get('logging', {})
        log_level = getattr(logging, logging_config.get('level', 'INFO'))

        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(log_level)

        # Configure formatter if specified
        if logging_config.get('log_format') == 'detailed':
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
        elif logging_config.get('log_format') == 'json':
            # Would implement JSON formatter here
            formatter = logging.Formatter('%(message)s')
        else:
            formatter = logging.Formatter('%(levelname)s - %(message)s')

    def process_signal(self,
                       signals: List[TargetWeightSignal],
                       current_portfolio: Dict[str, float],
                       market_data: Optional[Dict] = None) -> Dict:
        """Process target weight signals using configuration-driven pipeline"""

        start_time = datetime.now()

        try:
            # Check if we're in dry run mode
            if self.config.get('testing', {}).get('dry_run_mode', False):
                self.logger.info("Running in DRY RUN mode - no actual orders will be generated")

            # Step 1: Process alpha signals
            self.logger.debug("Processing alpha signals")
            target_portfolio, urgency_map, alpha_log = self.alpha_processor.process_signals(signals)

            # Step 2: Apply operational constraints if enabled
            if self.config.get('constraint_manager', {}).get('constraints', {}).get('enable_position_limits', True):
                self.logger.debug("Applying operational constraints")
                constrained_portfolio, constraint_log = self.constraint_manager.apply_operational_constraints(
                    target_portfolio, market_data
                )
            else:
                constrained_portfolio, constraint_log = target_portfolio, []

            # Step 3: Apply risk constraints if enabled
            if self.config.get('risk_manager', {}).get('firm_risk', {}).get('enable_firm_limits', True):
                self.logger.debug("Applying risk constraints")
                risk_constrained_portfolio, risk_log = self.risk_manager.apply_risk_constraints(
                    constrained_portfolio, market_data
                )
            else:
                risk_constrained_portfolio, risk_log = constrained_portfolio, []

            # Step 4: Solve for final portfolio
            self.logger.debug("Solving for final portfolio")
            final_portfolio, solver_log = self.solver.solve(risk_constrained_portfolio)

            # Step 5: Generate orders if not in dry run mode
            if not self.config.get('testing', {}).get('dry_run_mode', False):
                self.logger.debug("Generating orders")
                orders = self.order_generator.generate_orders(
                    final_portfolio, current_portfolio, urgency_map
                )
            else:
                orders = []
                self.logger.info("Skipping order generation (dry run mode)")

            # Step 6: Calculate attribution if enabled
            attribution = {}
            if self.config.get('attribution', {}).get('enable_performance_attribution', True):
                attribution = self._calculate_attribution(
                    target_portfolio, final_portfolio,
                    alpha_log + constraint_log + risk_log + solver_log
                )

            # Calculate processing time
            processing_time = (datetime.now() - start_time).total_seconds() * 1000

            # Check performance benchmarks
            max_processing_time = self.config.get('testing', {}).get('performance_benchmarks', {}).get(
                'max_processing_time_ms', 1000)
            if processing_time > max_processing_time:
                self.logger.warning(
                    f"Processing time {processing_time:.1f}ms exceeds benchmark {max_processing_time}ms")

            result = {
                'signal_type': 'target_weights',
                'engine_version': self.config['engine']['version'],
                'timestamp': datetime.now().isoformat(),
                'processing_time_ms': processing_time,
                'config_used': self._get_config_summary(),
                'raw_target_portfolio': target_portfolio,
                'final_target_portfolio': final_portfolio,
                'orders': orders,
                'attribution': attribution,
                'logs': {
                    'alpha_processing': alpha_log,
                    'constraints': constraint_log,
                    'risk_management': risk_log,
                    'solver': solver_log
                },
                'metadata': self._calculate_metadata(final_portfolio, current_portfolio, orders)
            }

            self.logger.info(f"Signal processing completed in {processing_time:.1f}ms")
            return result

        except Exception as e:
            self.logger.error(f"Error processing target weight signals: {e}")
            raise

    def _get_config_summary(self) -> Dict:
        """Get summary of key configuration parameters"""

        return {
            'aum': self.config.get('constraint_manager', {}).get('operational', {}).get('aum'),
            'max_position_size': self.config.get('constraint_manager', {}).get('operational', {}).get(
                'max_position_size'),
            'firm_max_position': self.config.get('risk_manager', {}).get('firm_risk', {}).get('max_single_position'),
            'risk_model': self.config.get('risk_manager', {}).get('risk_model', {}).get('type'),
            'solver_method': self.config.get('solver', {}).get('method'),
            'constraints_enabled': {
                'position_limits': self.config.get('constraint_manager', {}).get('constraints', {}).get(
                    'enable_position_limits'),
                'sector_limits': self.config.get('constraint_manager', {}).get('constraints', {}).get(
                    'enable_sector_limits'),
                'liquidity_limits': self.config.get('constraint_manager', {}).get('constraints', {}).get(
                    'enable_liquidity_limits'),
                'firm_limits': self.config.get('risk_manager', {}).get('firm_risk', {}).get('enable_firm_limits')
            }
        }

    def _calculate_attribution(self,
                               raw_portfolio: Dict[str, float],
                               final_portfolio: Dict[str, float],
                               all_logs: List[Dict]) -> Dict:
        """Calculate performance attribution using configured methods"""

        attribution_config = self.config.get('attribution', {})

        result = {}

        if attribution_config.get('enable_constraint_attribution', True):
            total_impact = sum(log.get('impact', 0) for log in all_logs if 'impact' in log)

            constraint_impacts = {}
            for log in all_logs:
                if 'constraint' in log or 'action' in log:
                    key = log.get('constraint', log.get('action', 'unknown'))
                    impact = log.get('impact', 0)

                    if key not in constraint_impacts:
                        constraint_impacts[key] = 0
                    constraint_impacts[key] += impact

            result.update({
                'total_constraint_impact': total_impact,
                'constraint_breakdown': constraint_impacts
            })

        if attribution_config.get('track_implementation_efficiency', True):
            similarity = self._calculate_similarity(raw_portfolio, final_portfolio)
            result['implementation_efficiency'] = similarity

        if attribution_config.get('metrics', {}).get('calculate_similarity', True):
            similarity_method = attribution_config.get('metrics', {}).get('similarity_method', 'manhattan')
            similarity = self._calculate_similarity(raw_portfolio, final_portfolio, method=similarity_method)
            result['portfolio_similarity'] = similarity

        return result

    def _calculate_similarity(self,
                              portfolio1: Dict[str, float],
                              portfolio2: Dict[str, float],
                              method: str = 'manhattan') -> float:
        """Calculate portfolio similarity using configured method"""

        all_symbols = set(list(portfolio1.keys()) + list(portfolio2.keys()))

        if not all_symbols:
            return 1.0

        if method == 'manhattan':
            total_diff = sum(abs(portfolio1.get(s, 0) - portfolio2.get(s, 0)) for s in all_symbols)
            max_diff = sum(abs(portfolio1.get(s, 0)) + abs(portfolio2.get(s, 0)) for s in all_symbols)
            return 1.0 - (total_diff / max_diff) if max_diff > 0 else 1.0

        elif method == 'euclidean':
            import math
            squared_diff = sum((portfolio1.get(s, 0) - portfolio2.get(s, 0)) ** 2 for s in all_symbols)
            max_squared_diff = sum((portfolio1.get(s, 0)) ** 2 + (portfolio2.get(s, 0)) ** 2 for s in all_symbols)
            return 1.0 - math.sqrt(squared_diff / max_squared_diff) if max_squared_diff > 0 else 1.0

        elif method == 'correlation':
            import numpy as np
            vec1 = [portfolio1.get(s, 0) for s in all_symbols]
            vec2 = [portfolio2.get(s, 0) for s in all_symbols]

            if len(vec1) > 1:
                correlation = np.corrcoef(vec1, vec2)[0, 1]
                return correlation if not np.isnan(correlation) else 0.0
            else:
                return 1.0 if vec1[0] == vec2[0] else 0.0

        else:
            # Default to manhattan
            return self._calculate_similarity(portfolio1, portfolio2, 'manhattan')

    def _calculate_metadata(self,
                            final_portfolio: Dict[str, float],
                            current_portfolio: Dict[str, float],
                            orders: List[Dict]) -> Dict:
        """Calculate metadata using configured metrics"""

        all_symbols = set(list(final_portfolio.keys()) + list(current_portfolio.keys()))

        metadata = {
            'positions_count': len(final_portfolio),
            'orders_count': len(orders),
            'gross_exposure': sum(abs(w) for w in final_portfolio.values()),
            'net_exposure': sum(final_portfolio.values())
        }

        # Add turnover if enabled
        if self.config.get('attribution', {}).get('metrics', {}).get('track_turnover', True):
            total_turnover = sum(abs(final_portfolio.get(s, 0) - current_portfolio.get(s, 0))
                                 for s in all_symbols)
            metadata['total_turnover'] = total_turnover

        # Add exposure changes if enabled
        if self.config.get('attribution', {}).get('metrics', {}).get('track_exposure_changes', True):
            old_gross = sum(abs(w) for w in current_portfolio.values())
            old_net = sum(current_portfolio.values())

            metadata.update({
                'gross_exposure_change': metadata['gross_exposure'] - old_gross,
                'net_exposure_change': metadata['net_exposure'] - old_net
            })

        # Add total notional if orders exist
        if orders:
            metadata['total_notional'] = sum(abs(order['delta_notional']) for order in orders)

        return metadata

    def get_config(self) -> Dict:
        """Get current configuration"""
        return self.config.copy()

    def update_config(self, config_overrides: Dict[str, Any]) -> None:
        """Update configuration with overrides"""
        self.config = ConfigLoader.override_config(self.config, config_overrides)

        # Reinitialize components with new config
        self.alpha_processor = AlphaProcessor(self.config)
        self.constraint_manager = ConstraintManager(self.config)
        self.risk_manager = RiskManager(self.config)
        self.solver = TargetWeightSolver(self.config)
        self.order_generator = OrderGenerator(self.config)

        self.logger.info("Configuration updated and components reinitialized")