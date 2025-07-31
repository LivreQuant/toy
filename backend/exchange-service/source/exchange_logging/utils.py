# source/logging/utils.py
import logging
import functools
import time
from typing import Any, Callable, Optional
from datetime import datetime
import traceback


class ExchangeLogger:
    """Enhanced logger with exchange-specific utilities"""

    def __init__(self, name: str):
        self.logger = logging.getLogger(name)
        self.name = name

    def trace_method(self, include_args: bool = True, include_result: bool = True):
        """Decorator to trace method calls with arguments and results"""

        def decorator(func: Callable) -> Callable:
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                start_time = time.time()

                # Log method entry
                if include_args:
                    args_str = self._format_args(args[1:], kwargs)  # Skip 'self'
                    self.logger.debug(f"ENTER {func.__name__}({args_str})")
                else:
                    self.logger.debug(f"ENTER {func.__name__}")

                try:
                    result = func(*args, **kwargs)
                    execution_time = (time.time() - start_time) * 1000

                    # Log method exit with result
                    if include_result and result is not None:
                        result_str = self._format_result(result)
                        self.logger.debug(f"EXIT  {func.__name__} -> {result_str} [{execution_time:.2f}ms]")
                    else:
                        self.logger.debug(f"EXIT  {func.__name__} [{execution_time:.2f}ms]")

                    return result

                except Exception as e:
                    execution_time = (time.time() - start_time) * 1000
                    self.logger.error(f"ERROR {func.__name__} -> {str(e)} [{execution_time:.2f}ms]")
                    self.logger.debug(f"STACK {func.__name__}:\n{traceback.format_exc()}")
                    raise

            return wrapper

        return decorator

    def log_calculation(self, description: str, inputs: dict, result: Any, details: Optional[dict] = None):
        """Log detailed calculation information"""
        self.logger.info(f"CALC: {description}")

        # Log inputs
        for key, value in inputs.items():
            self.logger.debug(f"  INPUT  {key}: {self._format_value(value)}")

        # Log additional details if provided
        if details:
            for key, value in details.items():
                self.logger.debug(f"  DETAIL {key}: {self._format_value(value)}")

        # Log result
        self.logger.info(f"  RESULT: {self._format_value(result)}")

    def log_state_change(self, object_name: str, old_state: dict, new_state: dict, change_reason: str = ""):
        """Log state changes with before/after comparison"""
        self.logger.info(f"STATE_CHANGE: {object_name} {change_reason}")

        # Find differences
        all_keys = set(old_state.keys()) | set(new_state.keys())

        for key in sorted(all_keys):
            old_val = old_state.get(key, "<missing>")
            new_val = new_state.get(key, "<missing>")

            if old_val != new_val:
                self.logger.info(f"  {key}: {self._format_value(old_val)} -> {self._format_value(new_val)}")

    def log_data_flow(self, source: str, destination: str, data_type: str, data_summary: str):
        """Log data flow between components"""
        self.logger.debug(f"DATA_FLOW: {source} -> {destination} | {data_type} | {data_summary}")

    def log_business_event(self, event_type: str, details: dict):
        """Log important business events"""
        self.logger.info(f"BIZ_EVENT: {event_type}")
        for key, value in details.items():
            self.logger.info(f"  {key}: {self._format_value(value)}")

    def log_performance(self, operation: str, duration_ms: float, additional_metrics: Optional[dict] = None):
        """Log performance metrics"""
        self.logger.info(f"PERF: {operation} took {duration_ms:.2f}ms")
        if additional_metrics:
            for metric, value in additional_metrics.items():
                self.logger.debug(f"  {metric}: {value}")

    def _format_args(self, args: tuple, kwargs: dict) -> str:
        """Format method arguments for logging"""
        arg_strs = []

        # Format positional args
        for arg in args:
            arg_strs.append(self._format_value(arg))

        # Format keyword args
        for key, value in kwargs.items():
            arg_strs.append(f"{key}={self._format_value(value)}")

        return ", ".join(arg_strs)

    def _format_result(self, result: Any) -> str:
        """Format method result for logging"""
        return self._format_value(result)

    def _format_value(self, value: Any) -> str:
        """Format a value for logging (truncate if too long)"""
        if value is None:
            return "None"

        # Handle common types
        if isinstance(value, (str, int, float, bool)):
            str_val = str(value)
        elif isinstance(value, dict):
            if len(value) <= 3:
                str_val = str(value)
            else:
                str_val = f"{{...{len(value)} items...}}"
        elif isinstance(value, (list, tuple)):
            if len(value) <= 3:
                str_val = str(value)
            else:
                str_val = f"[...{len(value)} items...]"
        else:
            str_val = str(type(value).__name__)

        # Truncate if too long
        if len(str_val) > 100:
            str_val = str_val[:97] + "..."

        return str_val

    # Delegate common logging methods
    def debug(self, msg: str, *args, **kwargs):
        self.logger.debug(msg, *args, **kwargs)

    def info(self, msg: str, *args, **kwargs):
        self.logger.info(msg, *args, **kwargs)

    def warning(self, msg: str, *args, **kwargs):
        self.logger.warning(msg, *args, **kwargs)

    def error(self, msg: str, *args, **kwargs):
        self.logger.error(msg, *args, **kwargs)

    def critical(self, msg: str, *args, **kwargs):
        self.logger.critical(msg, *args, **kwargs)


def get_exchange_logger(name: str) -> ExchangeLogger:
    """Get an enhanced logger for exchange components"""
    return ExchangeLogger(name)


def trace_execution(logger: logging.Logger):
    """Decorator for tracing function execution"""

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            logger.debug(f">>> Starting {func.__name__}")
            try:
                result = func(*args, **kwargs)
                duration = (time.time() - start_time) * 1000
                logger.debug(f"<<< Completed {func.__name__} in {duration:.2f}ms")
                return result
            except Exception as e:
                duration = (time.time() - start_time) * 1000
                logger.error(f"!!! Failed {func.__name__} after {duration:.2f}ms: {str(e)}")
                raise

        return wrapper

    return decorator