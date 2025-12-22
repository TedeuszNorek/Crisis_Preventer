"""Decorators for error handling and retries."""

import functools
import logging
import time
from typing import Type, Tuple, Optional, Any, Callable

from signalvortex.core.errors import SignalVortexError, DataSourceError

LOGGER = logging.getLogger(__name__)

def retry(
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
    tries: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    logger: Optional[logging.Logger] = None,
):
    """Retry decorator with exponential backoff.
    
    Args:
        exceptions: Tuple of exceptions to catch and retry.
        tries: Number of attempts.
        delay: Initial delay between retries in seconds.
        backoff: Multiplier for delay after each failure.
        logger: Logger to use for warnings (default: module logger).
    """
    if logger is None:
        logger = LOGGER

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            mtries, mdelay = tries, delay
            while mtries > 1:
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    msg = f"{func.__name__} failed: {e}, Retrying in {mdelay}s..."
                    logger.warning(msg)
                    time.sleep(mdelay)
                    mtries -= 1
                    mdelay *= backoff
            return func(*args, **kwargs)
        return wrapper
    return decorator

def safe_execute(
    default_return: Any = None,
    log_level: int = logging.ERROR,
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
):
    """Decorator to safely execute a function and return a default value on failure.
    
    Args:
        default_return: Value to return if exception occurs.
        log_level: Logging level for the error.
        exceptions: Tuple of exceptions to catch.
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except exceptions as e:
                LOGGER.log(log_level, f"Error in {func.__name__}: {e}", exc_info=True)
                return default_return
        return wrapper
    return decorator
