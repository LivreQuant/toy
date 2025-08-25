# source/common/dependencies.py
import logging
from typing import Dict, List, Any, Optional, Set
from enum import Enum
from dataclasses import dataclass
import asyncio

logger = logging.getLogger(__name__)

class DependencyStatus(Enum):
    PENDING = "pending"
    SATISFIED = "satisfied"
    FAILED = "failed"

@dataclass
class Dependency:
    name: str
    description: str
    check_function: callable
    required: bool = True
    timeout_seconds: int = 30
    retry_count: int = 3
    retry_delay: int = 5

class DependencyManager:
    """Manages service dependencies and health checks"""
    
    def __init__(self):
        self.dependencies: Dict[str, Dependency] = {}
        self.dependency_status: Dict[str, DependencyStatus] = {}
        self.dependency_results: Dict[str, Dict[str, Any]] = {}
        
    def register_dependency(self, dependency: Dependency):
        """Register a new dependency"""
        self.dependencies[dependency.name] = dependency
        self.dependency_status[dependency.name] = DependencyStatus.PENDING
        logger.info(f"📋 Registered dependency: {dependency.name}")
    
    async def check_all_dependencies(self) -> Dict[str, Any]:
        """Check all registered dependencies"""
        logger.info(f"🔍 Checking {len(self.dependencies)} dependencies")
        
        results = {
            "total_dependencies": len(self.dependencies),
            "satisfied_dependencies": 0,
            "failed_dependencies": 0,
            "all_critical_satisfied": True,
            "dependency_details": {}
        }
        
        # Check all dependencies in parallel
        check_tasks = []
        for dep_name, dependency in self.dependencies.items():
            task = asyncio.create_task(self._check_single_dependency(dependency))
            check_tasks.append((dep_name, task))
        
        # Wait for all checks to complete
        for dep_name, task in check_tasks:
            try:
                check_result = await task
                self.dependency_results[dep_name] = check_result
                
                if check_result['satisfied']:
                    self.dependency_status[dep_name] = DependencyStatus.SATISFIED
                    results["satisfied_dependencies"] += 1
                else:
                    self.dependency_status[dep_name] = DependencyStatus.FAILED
                    results["failed_dependencies"] += 1
                    
                    # Check if this is a critical dependency
                    if self.dependencies[dep_name].required:
                        results["all_critical_satisfied"] = False
                
                results["dependency_details"][dep_name] = check_result
                
            except Exception as e:
                logger.error(f"Error checking dependency {dep_name}: {e}")
                self.dependency_status[dep_name] = DependencyStatus.FAILED
                results["failed_dependencies"] += 1
                results["all_critical_satisfied"] = False
                
                results["dependency_details"][dep_name] = {
                    "satisfied": False,
                    "error": str(e),
                    "required": self.dependencies[dep_name].required
                }
        
        logger.info(f"✅ Dependency check complete: {results['satisfied_dependencies']}/{results['total_dependencies']} satisfied")
        return results
    
    async def _check_single_dependency(self, dependency: Dependency) -> Dict[str, Any]:
        """Check a single dependency with retries"""
        for attempt in range(dependency.retry_count):
            try:
                # Run the check function with timeout
                result = await asyncio.wait_for(
                    dependency.check_function(),
                    timeout=dependency.timeout_seconds
                )
                
                return {
                    "satisfied": True,
                    "result": result,
                    "attempts": attempt + 1,
                    "required": dependency.required,
                    "description": dependency.description
                }
                
            except asyncio.TimeoutError:
                logger.warning(f"⏰ Dependency check timeout: {dependency.name} (attempt {attempt + 1})")
                if attempt < dependency.retry_count - 1:
                    await asyncio.sleep(dependency.retry_delay)
                    continue
                else:
                    return {
                        "satisfied": False,
                        "error": f"Timeout after {dependency.timeout_seconds}s",
                        "attempts": attempt + 1,
                        "required": dependency.required,
                        "description": dependency.description
                    }
                    
            except Exception as e:
                logger.warning(f"❌ Dependency check failed: {dependency.name} - {e} (attempt {attempt + 1})")
                if attempt < dependency.retry_count - 1:
                    await asyncio.sleep(dependency.retry_delay)
                    continue
                else:
                    return {
                        "satisfied": False,
                        "error": str(e),
                        "attempts": attempt + 1,
                        "required": dependency.required,
                        "description": dependency.description
                    }
        
        # This shouldn't be reached, but just in case
        return {
            "satisfied": False,
            "error": "Max retries exceeded",
            "attempts": dependency.retry_count,
            "required": dependency.required,
            "description": dependency.description
        }
    
    def get_dependency_status(self, dependency_name: str) -> Optional[DependencyStatus]:
        """Get status of a specific dependency"""
        return self.dependency_status.get(dependency_name)
    
    def get_failed_dependencies(self) -> List[str]:
        """Get list of failed dependencies"""
        return [name for name, status in self.dependency_status.items() 
                if status == DependencyStatus.FAILED]
    
    def are_critical_dependencies_satisfied(self) -> bool:
        """Check if all critical dependencies are satisfied"""
        for dep_name, dependency in self.dependencies.items():
            if dependency.required and self.dependency_status.get(dep_name) != DependencyStatus.SATISFIED:
                return False
        return True

# Common dependency check functions
async def check_database_connectivity(db_manager):
    """Check database connectivity"""
    try:
        async with db_manager.pool.acquire() as conn:
            result = await conn.fetchrow("SELECT 1 as test")
            return {"status": "connected", "test_query": result['test']}
    except Exception as e:
        raise Exception(f"Database connectivity failed: {e}")

async def check_kubernetes_connectivity(k8s_manager):
    """Check Kubernetes connectivity"""
    try:
        # Try to list deployments to test connectivity
        deployments = k8s_manager.k8s_apps.list_namespaced_deployment(
            namespace=k8s_manager.namespace
        )
        return {
            "status": "connected", 
            "namespace": k8s_manager.namespace,
            "deployments_count": len(deployments.items)
        }
    except Exception as e:
        raise Exception(f"Kubernetes connectivity failed: {e}")

async def check_market_data_feeds():
    """Check market data feed availability"""
    # Simulate market data feed check
    await asyncio.sleep(0.1)  # Simulate network call
    
    feeds = ['BLOOMBERG', 'REFINITIV', 'ICE']
    feed_status = {}
    
    for feed in feeds:
        # Simulate feed check
        import random
        is_available = random.random() > 0.1  # 90% availability
        feed_status[feed] = {
            "available": is_available,
            "latency_ms": random.randint(10, 100) if is_available else None
        }
    
    # Check if at least one feed is available
    any_available = any(status["available"] for status in feed_status.values())
    
    if not any_available:
        raise Exception("No market data feeds available")
    
    return {"feeds": feed_status, "primary_feed": "BLOOMBERG"}

async def check_external_services():
    """Check external service dependencies"""
    services = {
        "auth_service": "http://auth-service:8000/health",
        "risk_service": "http://risk-service:8080/health", 
        "compliance_service": "http://compliance-service:9000/health"
    }
    
    service_status = {}
    for service_name, url in services.items():
        # Simulate HTTP health check
        await asyncio.sleep(0.05)  # Simulate network call
        
        import random
        is_healthy = random.random() > 0.05  # 95% availability
        service_status[service_name] = {
            "healthy": is_healthy,
            "url": url,
            "response_time_ms": random.randint(5, 50) if is_healthy else None
        }
    
    return {"services": service_status}