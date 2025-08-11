# source/engines/engine_factory.py
from typing import Dict, Optional
import logging
from source.engines.base_engine import BaseEngine
from source.engines.v01.engine import ENGINE_v01


class EngineFactory:
    """Factory for creating engine instances based on engine ID"""

    _engines = {
        1: ENGINE_v01,
        # Future engines will be added here:
        # 2: AdvancedTargetWeightEngine,
        # 3: RiskParityEngine,
        # etc.
    }

    @classmethod
    def create_engine(cls, engine_id: int, config: Dict = None) -> Optional[BaseEngine]:
        """
        Create an engine instance based on engine ID.

        Args:
            engine_id: Engine identifier from user database
            config: Optional engine-specific configuration

        Returns:
            Engine instance or None if engine_id not found
        """
        logger = logging.getLogger(cls.__name__)

        if engine_id not in cls._engines:
            logger.error(f"Unknown engine ID: {engine_id}")
            return None

        try:
            engine_class = cls._engines[engine_id]
            engine_instance = engine_class(config=config)
            logger.info(f"Created engine: {engine_class.__name__} (ID: {engine_id})")
            return engine_instance

        except Exception as e:
            logger.error(f"Failed to create engine {engine_id}: {e}")
            return None

    @classmethod
    def get_available_engines(cls) -> Dict[int, str]:
        """Get list of available engines"""
        return {engine_id: engine_class.__name__ for engine_id, engine_class in cls._engines.items()}