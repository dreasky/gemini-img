"""Base executor for browser automation tasks."""

from dataclasses import dataclass
from datetime import datetime
from typing import Callable, List, Optional

from .browser import BrowserManager
from .models import Task, TaskStatus, TaskStore


@dataclass
class ExecutionResult:
    """Result of batch execution."""

    total: int
    completed: int
    failed: int
    duration_seconds: float
    tasks: List[Task]


class BaseExecutor:
    """
    Base executor with browser management.

    Subclass and implement run_single_task():

        class MyExecutor(BaseExecutor):
            async def run_single_task(self, task: Task, page) -> Task:
                await page.fill("input", task.data)
                await page.click("button")
                task.status = TaskStatus.COMPLETED
                return task

    Usage:
        executor = MyExecutor(store, browser_manager)
        result = await executor.run_all()
    """

    def __init__(
        self,
        store: TaskStore,
        browser_manager: BrowserManager,
    ):
        self.store = store
        self.browser = browser_manager

    async def run_single_task(self, task: Task, page) -> Task:
        """
        Execute single task.

        Must be implemented by subclass.
        Should update task.status and return task.
        """
        raise NotImplementedError("Subclass must implement run_single_task()")

    async def run_task(self, task_id: str) -> Optional[Task]:
        """
        Run a task by ID with full setup/teardown.

        Returns completed/failed task or None if not found.
        """
        task = self.store.get(task_id)
        if not task:
            return None

        # Ensure browser is launched
        if not self.browser.is_launched:
            await self.browser.launch()

        page = await self.browser.new_page()

        try:
            result = await self.run_single_task(task, page)
        except Exception as e:
            task.status = TaskStatus.FAILED
            task.error = str(e)
            result = task
        finally:
            await page.close()
            self.store.save()

        return result

    async def run_all(
        self,
        on_progress: Optional[Callable[[Task, int, int], None]] = None,
        tasks: Optional[List[Task]] = None,
    ) -> ExecutionResult:
        """
        Run all pending tasks.

        Args:
            on_progress: Callback(task, done_count, total_count)
            tasks: Specific tasks to run (default: store.pending)

        Returns:
            ExecutionResult with statistics
        """
        start = datetime.now()

        # Get tasks to run
        if tasks is None:
            tasks = self.store.pending

        if not tasks:
            return ExecutionResult(
                total=0, completed=0, failed=0, duration_seconds=0, tasks=[]
            )

        # Ensure browser
        if not self.browser.is_launched:
            await self.browser.launch()

        completed = failed = 0
        results: List[Task] = []

        for i, task in enumerate(tasks, 1):
            result = await self.run_task(task.id)

            if result:
                results.append(result)
                if result.status == TaskStatus.COMPLETED:
                    completed += 1
                else:
                    failed += 1

            if on_progress:
                on_progress(result or task, i, len(tasks))

        await self.browser.close()

        duration = (datetime.now() - start).total_seconds()

        return ExecutionResult(
            total=len(tasks),
            completed=completed,
            failed=failed,
            duration_seconds=duration,
            tasks=results,
        )
