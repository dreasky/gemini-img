"""Gemini image generation package."""

from browser_scheduler import (
    BrowserManager,
    Context,
    ExecutionResult,
    Handler,
    Result,
    Task,
    TaskStatus,
    TaskStore,
    insert_text_with_newlines,
)

from .client import BrowserGenerationError, GeminiClient
from .executor import GeminiExecutor
from .handlers import GeminiHandler, GeminiStore
from .watermark import remove_gemini_watermark

__all__ = [
    # Core components (from browser_scheduler)
    "BrowserManager",
    "Context",
    "ExecutionResult",
    "Handler",
    "Result",
    "Task",
    "TaskStatus",
    "TaskStore",
    "insert_text_with_newlines",
    # Gemini-specific
    "BrowserGenerationError",
    "GeminiClient",
    "GeminiExecutor",
    "GeminiHandler",
    "GeminiStore",
    "remove_gemini_watermark",
]
