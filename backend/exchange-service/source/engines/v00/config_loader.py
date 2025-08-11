# source/conviction_engine/alpha_engines/target_weight/config_loader.py
import yaml
import os
from typing import Dict, Any, Optional
from pathlib import Path
import logging


class ConfigLoader:
    """Loads and validates configuration from YAML files"""

    def __init__(self, config_path: Optional[str] = None):
        if config_path is None:
            # Default to params.yaml in same directory
            config_path = Path(__file__).parent / "params.yaml"

        self.config_path = Path(config_path)
        self.logger = logging.getLogger(__name__)

        if not self.config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {self.config_path}")

    def load_config(self) -> Dict[str, Any]:
        """Load configuration from YAML file"""

        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)

            self.logger.info(f"Loaded configuration from {self.config_path}")

            # Validate configuration
            self._validate_config(config)

            return config

        except yaml.YAMLError as e:
            self.logger.error(f"Error parsing YAML configuration: {e}")
            raise
        except Exception as e:
            self.logger.error(f"Error loading configuration: {e}")
            raise

    def _validate_config(self, config: Dict[str, Any]) -> None:
        """Validate configuration structure and values"""

        required_sections = [
            'engine',
            'alpha_processor',
            'constraint_manager',
            'risk_manager',
            'solver',
            'order_generator'
        ]

        for section in required_sections:
            if section not in config:
                raise ValueError(f"Missing required configuration section: {section}")

        # Validate specific values
        self._validate_alpha_processor_config(config.get('alpha_processor', {}))
        self._validate_constraint_manager_config(config.get('constraint_manager', {}))
        self._validate_risk_manager_config(config.get('risk_manager', {}))
        self._validate_order_generator_config(config.get('order_generator', {}))

    def _validate_alpha_processor_config(self, config: Dict) -> None:
        """Validate alpha processor configuration"""

        validation = config.get('validation', {})

        if validation.get('max_individual_weight', 1.0) <= 0:
            raise ValueError("max_individual_weight must be positive")

        if validation.get('min_position_size', 0.001) < 0:
            raise ValueError("min_position_size must be non-negative")

        valid_urgencies = validation.get('valid_urgency_levels', [])
        if not isinstance(valid_urgencies, list) or len(valid_urgencies) == 0:
            raise ValueError("valid_urgency_levels must be a non-empty list")

    def _validate_constraint_manager_config(self, config: Dict) -> None:
        """Validate constraint manager configuration"""

        operational = config.get('operational', {})

        if operational.get('aum', 0) <= 0:
            raise ValueError("AUM must be positive")

        if not 0 < operational.get('target_leverage', 1.0) <= 5.0:
            raise ValueError("target_leverage must be between 0 and 5")

        if not 0 < operational.get('max_position_size', 0.1) <= 1.0:
            raise ValueError("max_position_size must be between 0 and 1")

    def _validate_risk_manager_config(self, config: Dict) -> None:
        """Validate risk manager configuration"""

        firm_risk = config.get('firm_risk', {})

        if not 0 < firm_risk.get('max_single_position', 0.05) <= 1.0:
            raise ValueError("max_single_position must be between 0 and 1")

        # Validate risk model type
        risk_model = config.get('risk_model', {})
        valid_risk_models = ['statistical', 'fama_french', 'barra', 'custom']

        if risk_model.get('type') not in valid_risk_models:
            raise ValueError(f"risk_model.type must be one of {valid_risk_models}")

    def _validate_order_generator_config(self, config: Dict) -> None:
        """Validate order generator configuration"""

        execution = config.get('execution', {})

        if execution.get('min_trade_size', 0) <= 0:
            raise ValueError("min_trade_size must be positive")

        # Validate urgency parameters
        urgency_params = config.get('urgency_parameters', {})

        for urgency, params in urgency_params.items():
            if not 0 < params.get('participation_rate', 0.1) <= 1.0:
                raise ValueError(f"participation_rate for {urgency} must be between 0 and 1")

            if params.get('max_duration_hours', 1) <= 0:
                raise ValueError(f"max_duration_hours for {urgency} must be positive")

    def get_config_value(self, config: Dict, key_path: str, default: Any = None) -> Any:
        """
        Get configuration value using dot notation

        Example: get_config_value(config, 'risk_manager.firm_risk.max_single_position', 0.05)
        """

        keys = key_path.split('.')
        value = config

        try:
            for key in keys:
                value = value[key]
            return value
        except (KeyError, TypeError):
            if default is not None:
                return default
            raise KeyError(f"Configuration key not found: {key_path}")

    @staticmethod
    def override_config(config: Dict, overrides: Dict[str, Any]) -> Dict:
        """
        Override configuration values with provided overrides

        Args:
            config: Base configuration
            overrides: Dictionary of overrides using dot notation keys
        """

        updated_config = config.copy()

        for key_path, value in overrides.items():
            keys = key_path.split('.')
            current = updated_config

            # Navigate to parent of target key
            for key in keys[:-1]:
                if key not in current:
                    current[key] = {}
                current = current[key]

            # Set the value
            current[keys[-1]] = value

        return updated_config