"""Gemini batch executor using BaseExecutor."""

from pathlib import Path
from typing import Optional

from browser_scheduler import (
    BaseExecutor,
    BrowserManager,
    Task,
    TaskStatus,
    insert_text_with_newlines,
)

from .config import GEMINI_URL, IMAGE_READY_SELECTOR, QUALITY_SUFFIX
from .handlers import GeminiHandler, GeminiStore
from .watermark import remove_gemini_watermark


class GeminiExecutor(BaseExecutor):
    """Execute Gemini image generation tasks.

    Delegates browser interactions to GeminiHandler to avoid duplicating
    selector knowledge and interaction logic.
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

        Reuses GeminiHandler's browser interaction methods so that
        selector/flow changes only need to be made in one place.
        """
        try:
            # Navigate — use domcontentloaded + selector wait instead of networkidle
            # (Gemini keeps WebSocket connections open, so networkidle always times out)
            await page.goto(GEMINI_URL, wait_until="domcontentloaded")
            await page.wait_for_timeout(2000)

            # Check session (after short wait for possible redirects)
            if "accounts.google.com" in page.url:
                task.status = TaskStatus.FAILED
                task.error = "Session expired - run login"
                return task

            # Wait for the initial input box (proves the page is ready)
            input_sel = await self.handler.wait_for_input_box(page)
            if not input_sel:
                task.status = TaskStatus.FAILED
                task.error = "Input box not found after page load"
                return task

            # Click tools button → make image chip
            if not await self.handler.click_tools_button(page):
                # Retry once after a longer wait
                await page.wait_for_timeout(10_000)
                if not await self.handler.click_tools_button(page):
                    task.status = TaskStatus.FAILED
                    task.error = "Failed to click tools button"
                    return task

            if not await self.handler.click_make_image_chip(page):
                task.status = TaskStatus.FAILED
                task.error = "Failed to click make image chip"
                return task

            # Wait for the image-generation input box to appear
            input_sel = await self.handler.wait_for_input_box(page, timeout=15_000)
            if not input_sel:
                task.status = TaskStatus.FAILED
                task.error = "Input box not found after clicking make image"
                return task

            # Focus the input box before inserting text
            input_box = await page.wait_for_selector(input_sel, timeout=5_000)
            await input_box.click()
            await page.wait_for_timeout(200)

            # Insert prompt text
            enhanced = self.handler._enhance_prompt(task.data)
            await insert_text_with_newlines(page, input_sel, enhanced)
            await page.wait_for_timeout(400)
            await page.keyboard.press("Enter")

            # Wait for generation
            if not await self.handler.wait_for_image_ready(page):
                task.status = TaskStatus.FAILED
                task.error = "Generation timeout"
                return task

            # Download
            img_data = await self.handler.download_image(page)
            if not img_data:
                task.status = TaskStatus.FAILED
                task.error = "Download failed"
                return task

            # Save
            if task.output_path:
                Path(task.output_path).parent.mkdir(parents=True, exist_ok=True)
                Path(task.output_path).write_bytes(img_data)
                remove_gemini_watermark(task.output_path)

            task.status = TaskStatus.COMPLETED

        except Exception as e:
            task.status = TaskStatus.FAILED
            task.error = str(e)

        return task
