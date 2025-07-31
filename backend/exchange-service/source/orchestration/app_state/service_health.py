# source/orchestration/app_state/service_health.py
"""
Service Health - Handles service status tracking
"""
import logging
from threading import RLock
from typing import Dict, Optional
from dataclasses import dataclass, field
from datetime import datetime

from source.utils.timezone_utils import now_utc


@dataclass
class ServiceStatus:
    """Tracks service health and status"""
    is_running: bool = False
    last_heartbeat: datetime = field(default_factory=lambda: now_utc())
    error_count: int = 0
    start_time: Optional[datetime] = None
    shutdown_time: Optional[datetime] = None

    def mark_started(self) -> None:
        self.is_running = True
        self.start_time = now_utc()
        self.error_count = 0
        self.last_heartbeat = now_utc()

    def mark_stopped(self) -> None:
        self.is_running = False
        self.shutdown_time = now_utc()

    def record_error(self, error: str) -> None:
        self.error_count += 1
        self.last_heartbeat = now_utc()


class ServiceHealth:
    def __init__(self):
        self._lock = RLock()
        self.logger = logging.getLogger(self.__class__.__name__)

        # Service status tracking
        self._service_status: Dict[str, ServiceStatus] = {
            'market_data_service': ServiceStatus(),
            'conviction_service': ServiceStatus(),
            'session_service': ServiceStatus()
        }
        self._initialization_errors: Dict[str, str] = {}

        # Market data service health
        self._market_data_service_available = False
        self._market_data_health_checker = None

    def mark_service_started(self, service_name: str):
        with self._lock:
            if service_name in self._service_status:
                self._service_status[service_name].mark_started()
            else:
                raise ValueError(f"Attempted to mark unknown service {service_name} as started")

    def mark_service_stopped(self, service_name: str):
        with self._lock:
            if service_name in self._service_status:
                self._service_status[service_name].mark_stopped()
            else:
                raise ValueError(f"Attempted to mark unknown service {service_name} as stopped")

    def record_initialization_error(self, service_name: str, error: str):
        with self._lock:
            self._initialization_errors[service_name] = error
            if service_name in self._service_status:
                self._service_status[service_name].record_error(error)
            raise ValueError(f"Initialization error for {service_name}: {error}")

    def get_service_status(self, service_name: str) -> Optional[ServiceStatus]:
        with self._lock:
            return self._service_status.get(service_name)

    def get_all_service_status(self):
        with self._lock:
            return {
                name: {
                    "running": status.is_running,
                    "errors": status.error_count,
                    "last_heartbeat": status.last_heartbeat.isoformat()
                }
                for name, status in self._service_status.items()
            }

    def is_healthy(self) -> bool:
        with self._lock:
            if not self._market_data_service_available:
                return False

            # Check if all required services are running
            required_services = {'market_data_service', 'conviction_service', 'session_service'}
            for service_name in required_services:
                status = self._service_status.get(service_name)
                if not status or not status.is_running:
                    return False

            return True

    def shutdown_all_services(self):
        with self._lock:
            for service_name in self._service_status:
                self.mark_service_stopped(service_name)

    def set_market_data_service_available(self, available: bool):
        with self._lock:
            self._market_data_service_available = available

    def is_market_data_service_available(self) -> bool:
        with self._lock:
            return self._market_data_service_available

    def set_market_data_health_checker(self, checker):
        with self._lock:
            self._market_data_health_checker = checker

    def get_health_status(self):
        with self._lock:
            health_status = {
                "services": self.get_all_service_status(),
                "errors": self._initialization_errors,
                "market_data_service": {
                    "available": self._market_data_service_available,
                    "health_checker_active": self._market_data_health_checker is not None
                }
            }

            # Add market data health checker status if available
            if self._market_data_health_checker:
                health_status["market_data_service"].update(
                    self._market_data_health_checker.get_status()
                )

            return health_status
