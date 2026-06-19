import time
import functools
import logging
from typing import Callable, Tuple, Type, Any


def retry(
    max_attempts: int = 3,
    delay: float = 1.5,
    backoff: float = 2.0,
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
):
    """Exponential-backoff retry decorator."""

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            log = logging.getLogger(func.__module__)
            wait = delay
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as exc:
                    if attempt == max_attempts:
                        log.error("%s failed after %d attempts: %s", func.__name__, max_attempts, exc)
                        raise
                    log.warning(
                        "%s attempt %d/%d failed: %s — retrying in %.1fs",
                        func.__name__, attempt, max_attempts, exc, wait,
                    )
                    time.sleep(wait)
                    wait *= backoff

        return wrapper

    return decorator
