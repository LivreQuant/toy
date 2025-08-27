# source/sod/system/database_validator.py
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


class DatabaseValidator:
    """Database validator"""

    def __init__(self, db_manager):
        self.db_manager = db_manager

    async def initialize(self):
        """Initialize database validator"""
        logger.info("🗄️ Database Validator initialized")

    async def validate_database(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Validate database integrity"""
        logger.info("🗄️ Validating database integrity")

        try:
            validation_results = {
                "table_checks": {},
                "constraint_checks": {},
                "data_integrity": {}
            }

            if self.db_manager and hasattr(self.db_manager, 'state'):
                # Run data integrity validation
                integrity_report = await self.db_manager.state.validate_data_integrity()
                validation_results["data_integrity"] = integrity_report

                # Check if there are critical issues
                if integrity_report.get("overall_status") != "HEALTHY":
                    logger.warning(f"Database integrity issues found: {integrity_report.get('issues', [])}")

                # Perform table maintenance
                await self.db_manager.state.vacuum_analyze_tables()

            logger.info("✅ Database validation completed")
            return validation_results

        except Exception as e:
            logger.error(f"❌ Database validation failed: {e}")
            raise