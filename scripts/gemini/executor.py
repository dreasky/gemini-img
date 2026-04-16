"""Gemini batch executor using BaseExecutor."""

from pathlib import Path
from typing import Optional

from browser_scheduler import (
    BaseExecutor,
    BrowserManager,
    Context,
    ExecutionResult,
    Task,
    TaskStatus,
    insert_text_with_newlines,
)

from .config import (
    CHAT_INPUT_SELECTOR,
    DOWNLOAD_BTN_SELECTOR,
    GEMINI_URL,
    IMAGE_ELEMENT_SELECTOR,
    IMAGE_READY_SELECTOR,
    MORE_MENU_SELECTOR,
    QUALITY_SUFFIX,
)
from .handlers import GeminiStore
from .watermark import remove_gemini_watermark


class GeminiExecutor(BaseExecutor):
    """Execute Gemini image generation tasks."""

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
        self.quality_suffix = QUALITY_SUFFIX

    def scan_prompts(self) -> int:
        """Scan for new prompt files."""
        return self.store.scan_files("*.md")

    def _enhance_prompt(self, prompt: str) -> str:
        """Add quality suffix."""
        if (
            "ultra sharp" not in prompt.lower()
            and "high definition" not in prompt.lower()
        ):
            return prompt + self.quality_suffix
        return prompt

    async def run_single_task(self, task: Task, page) -> Task:
        """Generate image for single task."""
        try:
            # Navigate
            await page.goto(GEMINI_URL, wait_until="domcontentloaded")
            await page.wait_for_timeout(2500)

            # Check session
            if "accounts.google.com" in page.url:
                task.status = TaskStatus.FAILED
                task.error = "Session expired - run login"
                return task

            # Input prompt directly (skip tool buttons for batch)
            enhanced = self._enhance_prompt(task.data)
            await insert_text_with_newlines(page, CHAT_INPUT_SELECTOR, enhanced)
            await page.wait_for_timeout(400)
            await page.keyboard.press("Enter")

            # Wait for generation
            try:
                await page.wait_for_selector(IMAGE_READY_SELECTOR, timeout=180000)
            except Exception:
                task.status = TaskStatus.FAILED
                task.error = "Generation timeout"
                return task

            # Download
            img_data = await self._download_image(page)
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

    async def _download_image(self, page) -> Optional[bytes]:
        """Download generated image."""
        images = []

        async def on_response(response):
            ct = response.headers.get("content-type", "")
            if any(t in ct for t in ("image/jpeg", "image/png", "image/webp")):
                try:
                    body = await response.body()
                    if len(body) >= 200000:
                        images.append((response.url, body))
                except Exception:
                    pass

        page.on("response", on_response)

        try:
            more_btn = await page.wait_for_selector(MORE_MENU_SELECTOR, timeout=10000)
            await more_btn.click()
            await page.wait_for_timeout(500)

            dl_btn = await page.wait_for_selector(DOWNLOAD_BTN_SELECTOR, timeout=10000)
            await dl_btn.click()

            for _ in range(60):
                if images:
                    break
                await page.wait_for_timeout(500)

        except Exception:
            pass
        finally:
            page.remove_listener("response", on_response)

        if images:
            return max(images, key=lambda x: len(x[1]))[1]

        # Fallback
        return await self._canvas_fallback(page)

    async def _canvas_fallback(self, page) -> Optional[bytes]:
        """Extract via canvas."""
        import base64

        try:
            b64 = await page.evaluate(
                f"""async () => {{
                const img = document.querySelector('{IMAGE_ELEMENT_SELECTOR}');
                if (!img) return null;
                try {{
                    const c = document.createElement('canvas');
                    c.width = img.naturalWidth;
                    c.height = img.naturalHeight;
                    c.getContext('2d').drawImage(img, 0, 0);
                    return c.toDataURL('image/jpeg', 0.95).split(',')[1];
                }} catch(e) {{}}
                return null;
            }}"""
            )
            if b64:
                return base64.b64decode(b64)
        except Exception:
            pass
        return None
