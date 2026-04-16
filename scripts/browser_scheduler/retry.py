"""Simple retry utility."""

import asyncio
from dataclasses import dataclass
from typing import Any, Callable, Optional


@dataclass
class RetryResult:
    """Result of a retry operation."""

    success: bool
    attempts: int
    error: Optional[str] = None
    result: Any = None


async def retry(
    fn: Callable,
    max_attempts: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
) -> RetryResult:
    """
    Retry an async function with exponential backoff.

    Args:
        fn: Async function to retry
        max_attempts: Maximum number of attempts
        delay: Initial delay between attempts (seconds)
        backoff: Multiplier for delay after each attempt

    Returns:
        RetryResult with success status and result/error
    """
    last_error = None

    for attempt in range(1, max_attempts + 1):
        try:
            result = await fn()
            return RetryResult(success=True, attempts=attempt, result=result)
        except Exception as e:
            last_error = str(e)
            if attempt < max_attempts:
                await asyncio.sleep(delay)
                delay *= backoff

    return RetryResult(success=False, attempts=max_attempts, error=last_error)


def retry_sync(
    fn: Callable,
    max_attempts: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
) -> RetryResult:
    """Synchronous version of retry."""
    import time

    last_error = None

    for attempt in range(1, max_attempts + 1):
        try:
            result = fn()
            return RetryResult(success=True, attempts=attempt, result=result)
        except Exception as e:
            last_error = str(e)
            if attempt < max_attempts:
                time.sleep(delay)
                delay *= backoff

    return RetryResult(success=False, attempts=max_attempts, error=last_error)
