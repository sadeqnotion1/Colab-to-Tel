# /content/Telegram-Leecher/colab_leecher/utility/logger.py

import logging
import time
from contextvars import ContextVar
from functools import wraps

# ContextVar to store request/task ID for log tracing
# This allows logs from different tasks to be easily filtered
request_id: ContextVar[str] = ContextVar('request_id', default='system')

class StructuredLogger:
    """
    Master-level Structured Logger for Production Observability.
    Supports request tracing and structured fields.
    """
    
    def __init__(self, name: str):
        self.logger = logging.getLogger(name)

    def _log(self, level: int, msg: str, **kwargs):
        rid = request_id.get()
        # Format extra fields as key=value for easy parsing
        extra_fields = " ".join(f"{k}={v}" for k, v in kwargs.items())
        full_msg = f"[{rid}] {msg}"
        if extra_fields:
            full_msg = f"{full_msg} | {extra_fields}"
        self.logger.log(level, full_msg)

    def info(self, msg: str, **kwargs):
        self._log(logging.INFO, msg, **kwargs)

    def error(self, msg: str, **kwargs):
        self._log(logging.ERROR, msg, **kwargs)

    def debug(self, msg: str, **kwargs):
        self._log(logging.DEBUG, msg, **kwargs)

    def warning(self, msg: str, **kwargs):
        self._log(logging.WARNING, msg, **kwargs)

    def critical(self, msg: str, **kwargs):
        self._log(logging.CRITICAL, msg, **kwargs)

def get_logger(name: str) -> StructuredLogger:
    """Factory function for StructuredLogger"""
    return StructuredLogger(name)

def timed_operation(operation_name: str):
    """
    Decorator to log the duration of an operation.
    Critical for identifying performance bottlenecks in production.
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            start = time.time()
            logger = get_logger(func.__module__)
            try:
                result = await func(*args, **kwargs)
                duration = time.time() - start
                logger.info(f"Operation {operation_name} completed", 
                           duration_ms=f"{duration*1000:.0f}",
                           status="success")
                return result
            except Exception as e:
                duration = time.time() - start
                logger.error(f"Operation {operation_name} failed", 
                            duration_ms=f"{duration*1000:.0f}",
                            status="error",
                            error=type(e).__name__)
                raise
        return wrapper
    return decorator
