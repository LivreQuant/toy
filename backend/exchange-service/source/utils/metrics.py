import time
import logging
from typing import Dict, Any, Optional, Callable
import functools
import asyncio

from source.utils.config import config

logger = logging.getLogger('metrics')

class Metrics:
    """Simple metrics collection and reporting"""
    
    _instance = None
    _counters = {}
    _gauges = {}
    _histograms = {}
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Metrics, cls).__new__(cls)
            cls._instance._enabled = config.enable_metrics
        return cls._instance
    
    def increment_counter(self, name: str, value: int = 1, tags: Optional[Dict[str, str]] = None) -> None:
        """Increment a counter metric"""
        if not self._enabled:
            return
        
        key = self._get_key(name, tags)
        self._counters[key] = self._counters.get(key, 0) + value
    
    def set_gauge(self, name: str, value: float, tags: Optional[Dict[str, str]] = None) -> None:
        """Set a gauge metric"""
        if not self._enabled:
            return
        
        key = self._get_key(name, tags)
        self._gauges[key] = value
    
    def observe_histogram(self, name: str, value: float, tags: Optional[Dict[str, str]] = None) -> None:
        """Add a value to a histogram metric"""
        if not self._enabled:
            return
        
        key = self._get_key(name, tags)
        if key not in self._histograms:
            self._histograms[key] = []
        self._histograms[key].append(value)
    
    def _get_key(self, name: str, tags: Optional[Dict[str, str]] = None) -> str:
        """Create a unique key for a metric"""
        if not tags:
            return name
        
        tag_str = ",".join(f"{k}={v}" for k, v in sorted(tags.items()))
        return f"{name}[{tag_str}]"
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get all metrics for reporting"""
        if not self._enabled:
            return {}
        
        return {
            "counters": self._counters.copy(),
            "gauges": self._gauges.copy(),
            "histograms": {k: self._summarize_histogram(v) for k, v in self._histograms.items()}
        }
    
    def _summarize_histogram(self, values: list) -> Dict[str, float]:
        """Summarize histogram values"""
        if not values:
            return {"count": 0}
        
        sorted_values = sorted(values)
        return {
            "count": len(values),
            "min": sorted_values[0],
            "max": sorted_values[-1],
            "avg": sum(values) / len(values),
            "p50": sorted_values[len(sorted_values) // 2],
            "p90": sorted_values[int(len(sorted_values) * 0.9)],
            "p99": sorted_values[int(len(sorted_values) * 0.99)]
        }

def timed(metric_name: str, tags: Optional[Dict[str, str]] = None):
    """Decorator to measure function execution time"""
    def decorator(func: Callable):
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            start_time = time.time()
            result = await func(*args, **kwargs)
            elapsed_ms = (time.time() - start_time) * 1000
            
            # Add metric
            metrics = Metrics()
            metrics.observe_histogram(
                f"{metric_name}_duration_ms", 
                elapsed_ms,
                tags
            )
            
            return result
        
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            start_time = time.time()
            result = func(*args, **kwargs)
            elapsed_ms = (time.time() - start_time) * 1000
            
            # Add metric
            metrics = Metrics()
            metrics.observe_histogram(
                f"{metric_name}_duration_ms", 
                elapsed_ms,
                tags
            )
            
            return result
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator