# source/common/metrics.py
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import time
import psutil
import asyncio

logger = logging.getLogger(__name__)

class MetricsCollector:
    """Collects and tracks system metrics"""
    
    def __init__(self):
        self.start_time = time.time()
        self.metrics_history: Dict[str, List[Dict[str, Any]]] = {}
        self.max_history_points = 1000  # Keep last 1000 data points
        
    async def initialize(self):
        """Initialize metrics collector"""
        logger.info("📊 Metrics Collector initialized")
    
    async def collect_system_metrics(self) -> Dict[str, Any]:
        """Collect system-wide metrics"""
        try:
            # System metrics
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            # Network stats
            network = psutil.net_io_counters()
            
            # Process metrics
            process = psutil.Process()
            process_memory = process.memory_info()
            
            metrics = {
                "timestamp": datetime.utcnow().isoformat(),
                "system": {
                    "cpu_percent": cpu_percent,
                    "memory_percent": memory.percent,
                    "memory_available_gb": memory.available / (1024**3),
                    "disk_percent": (disk.used / disk.total) * 100,
                    "disk_free_gb": disk.free / (1024**3)
                },
                "network": {
                    "bytes_sent": network.bytes_sent,
                    "bytes_recv": network.bytes_recv,
                    "packets_sent": network.packets_sent,
                    "packets_recv": network.packets_recv
                },
                "process": {
                    "memory_rss_mb": process_memory.rss / (1024**2),
                    "memory_vms_mb": process_memory.vms / (1024**2),
                    "cpu_percent": process.cpu_percent(),
                    "num_threads": process.num_threads()
                },
                "uptime_seconds": time.time() - self.start_time
            }
            
            # Store in history
            self._store_metric("system_metrics", metrics)
            
            return metrics
            
        except Exception as e:
            logger.error(f"❌ Failed to collect system metrics: {e}", exc_info=True)
            return {}
    
    async def update_health_metrics(self):
        """Update health check metrics"""
        try:
            # Simulate health check metrics
            health_metrics = {
                "timestamp": datetime.utcnow().isoformat(),
                "database_connection_pool": {
                    "active_connections": 8,
                    "idle_connections": 12,
                    "max_connections": 20
                },
                "kubernetes_status": {
                    "running_pods": 15,
                    "pending_pods": 0,
                    "failed_pods": 0
                },
                "market_data_feeds": {
                    "active_feeds": 3,
                    "failed_feeds": 0,
                    "avg_latency_ms": 25
                }
            }
            
            self._store_metric("health_metrics", health_metrics)
            
        except Exception as e:
            logger.error(f"❌ Failed to update health metrics: {e}", exc_info=True)
    
    def record_operation_metric(self, operation: str, duration_seconds: float,
                               success: bool, context: Dict[str, Any] = None):
        """Record metrics for a specific operation"""
        try:
            metric = {
                "timestamp": datetime.utcnow().isoformat(),
                "operation": operation,
                "duration_seconds": duration_seconds,
                "success": success,
                "context": context or {}
            }
            
            self._store_metric(f"operation_{operation}", metric)
            
            # Also store in general operations metric
            self._store_metric("operations", metric)
            
        except Exception as e:
            logger.error(f"❌ Failed to record operation metric: {e}", exc_info=True)
    
    def record_workflow_metric(self, workflow_name: str, task_count: int,
                             duration_seconds: float, success: bool,
                             failed_tasks: int = 0):
        """Record workflow execution metrics"""
        try:
            metric = {
                "timestamp": datetime.utcnow().isoformat(),
                "workflow": workflow_name,
                "total_tasks": task_count,
                "failed_tasks": failed_tasks,
                "success_rate": (task_count - failed_tasks) / task_count if task_count > 0 else 0,
                "duration_seconds": duration_seconds,
                "success": success
            }
            
            self._store_metric("workflows", metric)
            self._store_metric(f"workflow_{workflow_name}", metric)
            
        except Exception as e:
            logger.error(f"❌ Failed to record workflow metric: {e}", exc_info=True)
    
    def record_business_metric(self, metric_name: str, value: float,
                             unit: str = None, tags: Dict[str, str] = None):
        """Record business-level metrics"""
        try:
            metric = {
                "timestamp": datetime.utcnow().isoformat(),
                "metric_name": metric_name,
                "value": value,
                "unit": unit,
                "tags": tags or {}
            }
            
            self._store_metric("business_metrics", metric)
            self._store_metric(f"business_{metric_name}", metric)
            
        except Exception as e:
            logger.error(f"❌ Failed to record business metric: {e}", exc_info=True)
    
    def _store_metric(self, metric_type: str, metric_data: Dict[str, Any]):
        """Store metric in history with size limits"""
        if metric_type not in self.metrics_history:
            self.metrics_history[metric_type] = []
        
        self.metrics_history[metric_type].append(metric_data)
        
        # Trim history if too large
        if len(self.metrics_history[metric_type]) > self.max_history_points:
            self.metrics_history[metric_type] = self.metrics_history[metric_type][-self.max_history_points:]
    
    def get_metric_history(self, metric_type: str, 
                          hours_back: int = 24) -> List[Dict[str, Any]]:
        """Get metric history for a specific time period"""
        if metric_type not in self.metrics_history:
            return []
        
        cutoff_time = datetime.utcnow() - timedelta(hours=hours_back)
        
        filtered_metrics = []
        for metric in self.metrics_history[metric_type]:
            try:
                metric_time = datetime.fromisoformat(metric['timestamp'].replace('Z', '+00:00'))
                if metric_time >= cutoff_time:
                    filtered_metrics.append(metric)
            except (KeyError, ValueError):
                continue
        
        return filtered_metrics
    
    def get_uptime(self) -> float:
        """Get system uptime in seconds"""
        return time.time() - self.start_time
    
    def get_latest_metrics(self) -> Dict[str, Any]:
        """Get latest metrics for all types"""
        latest_metrics = {}
        
        for metric_type, history in self.metrics_history.items():
            if history:
                latest_metrics[metric_type] = history[-1]
        
        return latest_metrics
    
    def get_metric_summary(self, metric_type: str = None) -> Dict[str, Any]:
        """Get summary statistics for metrics"""
        summary = {
            "total_metric_types": len(self.metrics_history),
            "uptime_seconds": self.get_uptime()
        }
        
        if metric_type and metric_type in self.metrics_history:
            history = self.metrics_history[metric_type]
            summary[metric_type] = {
                "data_points": len(history),
                "latest_timestamp": history[-1]["timestamp"] if history else None,
                "oldest_timestamp": history[0]["timestamp"] if history else None
            }
        else:
            # Summary for all metric types
            by_type = {}
            for mtype, history in self.metrics_history.items():
                by_type[mtype] = {
                    "data_points": len(history),
                    "latest_timestamp": history[-1]["timestamp"] if history else None
                }
            summary["by_type"] = by_type
        
        return summary