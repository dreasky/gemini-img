"""Retry mechanism with exponential backoff for browser operations."""

import asyncio
import random
from typing import Callable, TypeVar

from .client import BrowserGenerationError
from .task_manager import Task, TaskStatus

T = TypeVar("T")


class RetryHandler:
    """Retry handler with exponential backoff and jitter."""

    def __init__(
        self,
        max_retries:     int   = 2,
        base_delay:      float = 5.0,
        max_delay:       float = 60.0,
        exponential_base: float = 2.0,
    ) -> None:
        self.max_retries      = max_retries
        self.base_delay       = base_delay
        self.max_delay        = max_delay
        self.exponential_base = exponential_base

    def _delay(self, attempt: int) -> float:
        delay  = self.base_delay * (self.exponential_base ** attempt)
        delay  = min(delay, self.max_delay)
        jitter = delay * random.uniform(0, 0.25)
        return delay + jitter

    async def execute_with_retry(self, func: Callable[[], T], task: Task) -> T:
        """Execute *func* (no-arg async callable) with retry on transient errors.

        Args:
            func:  Zero-argument async callable to execute.
            task:  Task being processed — status/retry_count are updated in-place.

        Raises:
            BrowserGenerationError: When all retries are exhausted or error is non-retryable.
        """
        last_error: Exception | None = None

        for attempt in range(self.max_retries + 1):
            try:
                return await func()

            except BrowserGenerationError as e:
                last_error = e
                if not e.retryable or attempt >= self.max_retries:
                    raise
                task.retry_count = attempt + 1
                task.status      = TaskStatus.RETRYING.value
                await asyncio.sleep(self._delay(attempt))

            except Exception as e:
                last_error = BrowserGenerationError(str(e), retryable=True)
                if attempt >= self.max_retries:
                    raise BrowserGenerationError(str(e), retryable=False) from e
                task.retry_count = attempt + 1
                task.status      = TaskStatus.RETRYING.value
                await asyncio.sleep(self._delay(attempt))

        raise last_error  # type: ignore[misc]
