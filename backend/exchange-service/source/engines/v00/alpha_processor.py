# source/conviction_engine/alpha_engines/target_weight/alpha_processor.py
from typing import Dict, List, Tuple
from dataclasses import dataclass
import logging


@dataclass
class TargetWeightSignal:
    """Input signal for target weight engine"""
    symbol: str
    target_weight: float
    urgency: str

    def __post_init__(self):
        # Validation will be done by processor using config
        pass


class AlphaProcessor:
    """Processes and validates raw alpha signals using configuration"""

    def __init__(self, config: Dict):
        self.config = config
        self.logger = logging.getLogger(__name__)

        # Extract configuration values
        self.validation_config = config.get('alpha_processor', {}).get('validation', {})
        self.signal_config = config.get('alpha_processor', {}).get('signal_processing', {})
        self.logging_config = config.get('alpha_processor', {}).get('logging', {})

        # Set logging level from config
        log_level = getattr(logging, self.logging_config.get('log_level', 'INFO'))
        self.logger.setLevel(log_level)

    def process_signals(self, signals: List[TargetWeightSignal]) -> Tuple[Dict[str, float], Dict[str, str], List[Dict]]:
        """Process raw alpha signals into target portfolio"""

        validation_log = []

        # Validate signals using config
        validated_signals = self._validate_signals(signals, validation_log)

        # Convert to portfolio dict
        target_portfolio = {signal.symbol: signal.target_weight
                            for signal in validated_signals}

        # Create urgency mapping
        urgency_map = {signal.symbol: signal.urgency
                       for signal in validated_signals}

        # Validate portfolio-level constraints
        self._validate_portfolio(target_portfolio, validation_log)

        return target_portfolio, urgency_map, validation_log

    def _validate_signals(self, signals: List[TargetWeightSignal], log: List[Dict]) -> List[TargetWeightSignal]:
        """Validate individual signals using configuration"""

        valid_signals = []
        seen_symbols = set()

        # Get config values
        max_individual_weight = self.validation_config.get('max_individual_weight', 1.0)
        min_position_size = self.validation_config.get('min_position_size', 0.001)
        valid_urgencies = self.validation_config.get('valid_urgency_levels', ['HIGH', 'MEDIUM', 'LOW'])
        allow_duplicates = self.signal_config.get('allow_duplicate_symbols', False)
        duplicate_action = self.signal_config.get('duplicate_action', 'use_last')
        filter_tiny = self.signal_config.get('filter_tiny_positions', True)

        for signal in signals:
            # Validate urgency
            if signal.urgency not in valid_urgencies:
                log.append({
                    'type': 'error',
                    'component': 'alpha_processor',
                    'issue': 'invalid_urgency',
                    'symbol': signal.symbol,
                    'urgency': signal.urgency,
                    'valid_urgencies': valid_urgencies
                })
                continue

            # Check for duplicates
            if signal.symbol in seen_symbols:
                if not allow_duplicates:
                    if duplicate_action == 'use_last':
                        # Remove previous occurrence
                        valid_signals = [s for s in valid_signals if s.symbol != signal.symbol]
                        log.append({
                            'type': 'warning',
                            'component': 'alpha_processor',
                            'issue': 'duplicate_symbol',
                            'symbol': signal.symbol,
                            'action': 'using_last_occurrence'
                        })
                    elif duplicate_action == 'use_first':
                        log.append({
                            'type': 'warning',
                            'component': 'alpha_processor',
                            'issue': 'duplicate_symbol',
                            'symbol': signal.symbol,
                            'action': 'using_first_occurrence'
                        })
                        continue
                    elif duplicate_action == 'error':
                        log.append({
                            'type': 'error',
                            'component': 'alpha_processor',
                            'issue': 'duplicate_symbol',
                            'symbol': signal.symbol,
                            'action': 'error'
                        })
                        continue

            seen_symbols.add(signal.symbol)

            # Validate weight bounds
            if abs(signal.target_weight) > max_individual_weight:
                log.append({
                    'type': 'error',
                    'component': 'alpha_processor',
                    'issue': 'weight_too_large',
                    'symbol': signal.symbol,
                    'weight': signal.target_weight,
                    'max_allowed': max_individual_weight
                })
                continue

            # Filter tiny positions if enabled
            if filter_tiny and abs(signal.target_weight) < min_position_size:
                if self.logging_config.get('log_filtered_positions', True):
                    log.append({
                        'type': 'info',
                        'component': 'alpha_processor',
                        'issue': 'position_too_small',
                        'symbol': signal.symbol,
                        'weight': signal.target_weight,
                        'min_required': min_position_size,
                        'action': 'filtered_out'
                    })
                continue

            valid_signals.append(signal)

        return valid_signals

    def _validate_portfolio(self, portfolio: Dict[str, float], log: List[Dict]) -> None:
        """Validate portfolio-level constraints using configuration"""

        # Check gross exposure
        gross_exposure = sum(abs(w) for w in portfolio.values())
        max_gross = self.validation_config.get('max_total_gross_exposure', 2.0)

        if gross_exposure > max_gross:
            log.append({
                'type': 'error',
                'component': 'alpha_processor',
                'issue': 'gross_exposure_too_high',
                'gross_exposure': gross_exposure,
                'max_allowed': max_gross
            })

        # Check leverage deviation
        net_exposure = sum(portfolio.values())
        target_leverage = self.config.get('constraint_manager', {}).get('operational', {}).get('target_leverage', 1.0)
        max_deviation = self.validation_config.get('max_leverage_deviation', 0.05)

        if abs(net_exposure - target_leverage) > max_deviation:
            log.append({
                'type': 'warning',
                'component': 'alpha_processor',
                'issue': 'leverage_deviation',
                'net_exposure': net_exposure,
                'target_leverage': target_leverage,
                'deviation': abs(net_exposure - target_leverage)
            })