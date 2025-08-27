# source/sod/system/health_checker.py
import logging
from typing import Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)


class SystemHealthChecker:
    """System health checker"""

    def __init__(self, db_manager, k8s_manager):
        self.db_manager = db_manager
        self.k8s_manager = k8s_manager

    async def initialize(self):
        """Initialize system health checker"""
        logger.info("🔍 System Health Checker initialized")

    async def check_system_health(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Perform system health check"""
        logger.info("🔍 Performing system health check")

        try:
            health_results = {
                "database_connectivity": False,
                "kubernetes_connectivity": False,
                "alerts": []
            }

            # Check database connectivity
            if self.db_manager:
                try:
                    result = await self.db_manager.state.fetch_one("SELECT 1 as test")
                    health_results["database_connectivity"] = result is not None
                    logger.info("✅ Database connectivity check passed")
                except Exception as e:
                    health_results["alerts"].append(f"Database connectivity issue: {e}")
                    logger.error(f"❌ Database connectivity check failed: {e}")

            # Check Kubernetes connectivity
            if self.k8s_manager:
                try:
                    await self.k8s_manager.check_cluster_health()
                    health_results["kubernetes_connectivity"] = True
                    logger.info("✅ Kubernetes connectivity check passed")
                except Exception as e:
                    health_results["alerts"].append(f"Kubernetes connectivity issue: {e}")
                    logger.error(f"❌ Kubernetes connectivity check failed: {e}")

            # Determine overall health
            overall_health = (health_results["database_connectivity"] and
                              health_results["kubernetes_connectivity"] and
                              len(health_results["alerts"]) == 0)

            if not overall_health:
                raise Exception(f"System health check failed: {health_results['alerts']}")

            logger.info("✅ System health check passed")
            return health_results

        except Exception as e:
            logger.error(f"❌ System health check failed: {e}")
            raise