# source/common/metrics.py
import logging
from typing import Dict, Any
from datetime import datetime
from collections import defaultdict, deque

logger = logging.getLogger(__name__)


class SimpleMetrics:
    """Simple metrics collector - no fancy monitoring bullshit"""

    def __init__(self):
        self.counters: Dict[str, int] = defaultdict(int)
        self.timers: Dict[str, deque] = defaultdict(lambda: deque(maxlen=100))
        self.gauges: Dict[str, float] = {}

    def increment(self, metric_name: str, value: int = 1):
        """Increment a counter"""
        self.counters[metric_name] += value
        logger.debug(f"📊 Counter {metric_name}: {self.counters[metric_name]}")

    def set_gauge(self, metric_name: str, value: float):
        """Set a gauge value"""
        self.gauges[metric_name] = value
        logger.debug(f"📊 Gauge {metric_name}: {value}")

    def record_timing(self, metric_name: str, duration_seconds: float):
        """Record timing data"""
        self.timers[metric_name].append(duration_seconds)
        logger.debug(f"📊 Timing {metric_name}: {duration_seconds:.2f}s")

    def get_counter(self, metric_name: str) -> int:
        """Get counter value"""
        return self.counters.get(metric_name, 0)

    def get_gauge(self, metric_name: str) -> float:
        """Get gauge value"""
        return self.gauges.get(metric_name, 0.0)

    def get_avg_timing(self, metric_name: str) -> float:
        """Get average timing"""
        timings = self.timers.get(metric_name, [])
        return sum(timings) / len(timings) if timings else 0.0

    def get_summary(self) -> Dict[str, Any]:
        """Get metrics summary"""
        return {
            "counters": dict(self.counters),
            "gauges": dict(self.gauges),
            "timing_averages": {
                name: self.get_avg_timing(name)
                for name in self.timers.keys()
            }
        }

    def log_summary(self):
        """Log metrics summary"""
        summary = self.get_summary()
        logger.info(f"📊 Metrics Summary: {summary}")


# Global metrics instance
metrics = SimpleMetrics()


# Convenience functions
def increment_counter(name: str, value: int = 1):
    metrics.increment(name, value)


def set_gauge(name: str, value: float):
    metrics.set_gauge(name, value)


def record_timing(name: str, duration: float):
    metrics.record_timing(name, duration)


# Context manager for timing
class timer:
    def __init__(self, metric_name: str):
        self.metric_name = metric_name
        self.start_time = None

    def __enter__(self):
        self.start_time = datetime.utcnow()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.start_time:
            duration = (datetime.utcnow() - self.start_time).total_seconds()
            record_timing(self.metric_name, duration)