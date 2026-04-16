"""Simple handler framework for browser automation."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Optional

from .models import Task


@dataclass
class Context:
    """Execution context."""

    task: Task
    page: Any = None


@dataclass
class Result:
    """Execution result."""

    success: bool = True
    error: Optional[str] = None


class Handler(ABC):
    """
    Base handler for task execution.

    Subclass and implement execute():

        class MyHandler(Handler):
            async def execute(self, ctx: Context) -> Result:
                await ctx.page.fill("input", ctx.task.prompt_content)
                await ctx.page.click("button")
                return Result()
    """

    @abstractmethod
    async def execute(self, ctx: Context) -> Result:
        """Execute the task. Must be implemented by subclass."""
        pass
