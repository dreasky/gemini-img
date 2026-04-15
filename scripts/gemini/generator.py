"""Batch image generator using the headless browser client."""

import asyncio
from dataclasses import dataclass
from datetime import datetime
from typing import Callable, List, Optional

from .client import BrowserGenerationError, GeminiImageGenerator
from .config import BrowserConfig
from .retry import RetryHandler
from .task_manager import Task, TaskManager, TaskStatus


@dataclass
class BatchResult:
    """Summary of a batch generation run."""

    total: int
    completed: int
    failed: int
    tasks: List[Task]


class BrowserImageGenerator:
    """Sequential batch generator — wraps GeminiImageGenerator with task management.

    Browser automation cannot be parallelised safely (single authenticated
    session), so tasks are processed one at a time.
    """

    def __init__(self, config: BrowserConfig, task_manager: TaskManager) -> None:
        self.config = config
        self.task_manager = task_manager
        self.browser_gen = GeminiImageGenerator(headless=config.headless)
        self.retry = RetryHandler(
            max_retries=config.max_retries,
            base_delay=config.retry_delay,
        )

    # ── single task ────────────────────────────────────────────────────────────

    async def generate_single(self, task: Task) -> Task:
        """Generate the image for *task*, update its status, and return it."""
        task.status = TaskStatus.RUNNING.value
        self.task_manager.update_task(task)

        try:

            async def _do() -> None:
                results = await self.browser_gen.generate_async(
                    task.prompt_content,
                    task.output_path,
                    count=1,
                )
                if not results:
                    raise BrowserGenerationError(
                        "Generator returned no output files",
                        retryable=True,
                    )

            await self.retry.execute_with_retry(_do, task)
            task.status = TaskStatus.COMPLETED.value
            task.completed_at = datetime.now().isoformat()
            task.error = None

        except Exception as e:
            task.status = TaskStatus.FAILED.value
            task.error = str(e)
            task.completed_at = datetime.now().isoformat()

        self.task_manager.update_task(task)
        return task

    # ── batch ──────────────────────────────────────────────────────────────────

    async def generate_batch(
        self,
        tasks: Optional[List[Task]] = None,
        on_progress: Optional[Callable[[Task, int, int], None]] = None,
    ) -> BatchResult:
        """Process *tasks* sequentially; call *on_progress(task, done, total)* after each."""
        if tasks is None:
            tasks = self.task_manager.get_pending_tasks()
        if not tasks:
            return BatchResult(total=0, completed=0, failed=0, tasks=[])

        completed = failed = 0
        for i, task in enumerate(tasks, 1):
            result = await self.generate_single(task)
            if result.status == TaskStatus.COMPLETED.value:
                completed += 1
            else:
                failed += 1
            if on_progress:
                on_progress(result, i, len(tasks))

        return BatchResult(
            total=len(tasks), completed=completed, failed=failed, tasks=tasks
        )

    async def process_all(
        self,
        on_progress: Optional[Callable[[Task, int, int], None]] = None,
    ) -> BatchResult:
        """Scan for new .md prompt files, then process all pending tasks."""
        self.task_manager.scan_prompts()
        self.task_manager.load_tasks()
        pending = self.task_manager.get_pending_tasks()
        if not pending:
            return BatchResult(total=0, completed=0, failed=0, tasks=[])
        from .utils import print_status

        print_status(self.task_manager)
        return await self.generate_batch(pending, on_progress=on_progress)
