"""
Simple browser automation task scheduler.

Basic usage:
    from browser_scheduler import Task, TaskStatus, Handler, Context, Store, retry

    class MyHandler(Handler):
        async def execute(self, ctx: Context) -> Result:
            await ctx.page.fill("input", ctx.task.data)
            return Result()

    store = Store("tasks.json")
    store.add(Task(id="1", data="hello"))
    store.save()

Advanced usage with BrowserManager and FileScanningStore:
    from browser_scheduler import (
        BrowserManager, FileScanningStore, BaseExecutor,
    )

    # Scan files to create tasks
    store = FileScanningStore("tasks.json", "./prompts")
    store.scan_files("*.md")

    # Execute with managed browser
    browser = BrowserManager(".data/session.json")
    executor = MyExecutor(store, browser)
    result = await executor.run_all()
"""

# Core components
from .handlers import Context, Handler, Result
from .models import Task, TaskStatus, TaskStore
from .retry import retry, retry_sync, RetryResult
from .utils import insert_text_with_newlines, clear_contenteditable

# Extended components
from .browser import BrowserManager
from .executor import BaseExecutor, ExecutionResult

__all__ = [
    # Models
    "Task",
    "TaskStatus",
    "TaskStore",
    # Handlers
    "Handler",
    "Context",
    "Result",
    "TaskStore",
    # Retry
    "retry",
    "retry_sync",
    "RetryResult",
    # Utils
    "insert_text_with_newlines",
    "clear_contenteditable",
    # Extended
    "BrowserManager",
    "BaseExecutor",
    "ExecutionResult",
]
