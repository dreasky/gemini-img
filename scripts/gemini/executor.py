"""Gemini batch executor using BaseExecutor."""

from pathlib import Path
from typing import Optional

from browser_scheduler import (
    BaseExecutor,
    BrowserManager,
    Context,
    Task,
    TaskStatus,
)

from .config import QUALITY_SUFFIX
from .handlers import GeminiHandler, GeminiStore


class GeminiExecutor(BaseExecutor):
    """Execute Gemini image generation tasks.

    Delegates ALL browser interaction to GeminiHandler.execute().
    This class only provides: store, browser lifecycle, task state management.
    """

    def __init__(
        self,
        input_dir: Path,
        output_dir: Optional[Path] = None,
        headless: bool = True,
    ):
        store = GeminiStore(input_dir, output_dir)

        skill_dir = Path(__file__).parent.parent.parent
        storage_path = skill_dir / ".data" / "storage_state.json"
        browser = BrowserManager(
            storage_path=storage_path,
            headless=headless,
        )

        super().__init__(store=store, browser_manager=browser)
        self.handler = GeminiHandler(quality_suffix=QUALITY_SUFFIX)

    def scan_prompts(self) -> int:
        """Scan for new prompt files."""
        return self.store.scan_files("*.md")

    async def run_single_task(self, task: Task, page) -> Task:
        """Generate image for single task.

        Delegates to GeminiHandler.execute() which handles the entire
        browser flow (navigate → tools → input → generate → download → save).
        """
        ctx = Context(task=task, page=page)
        result = await self.handler.execute(ctx)

        if result.success:
            task.status = TaskStatus.COMPLETED
        else:
            task.status = TaskStatus.FAILED
            task.error = result.error

        return task
