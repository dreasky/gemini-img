"""Simple Gemini client for single image generation."""

import asyncio
from datetime import datetime
from pathlib import Path
from typing import Optional

from browser_scheduler import BrowserManager, Context, Task

from .config import GEMINI_URL
from .handlers import GeminiHandler


class BrowserGenerationError(Exception):
    """Browser generation failed."""

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class GeminiClient:
    """Simple client for single image generation."""

    def __init__(self, headless: bool = True):
        self.headless = headless
        self.handler = GeminiHandler()

    def _get_storage_path(self) -> Path:
        """Get storage state path."""
        skill_dir = Path(__file__).parent.parent.parent
        return skill_dir / ".data" / "storage_state.json"

    def login(self) -> None:
        """Login and save session."""
        browser = BrowserManager(
            storage_path=self._get_storage_path(),
            headless=False,
        )
        browser.login_sync(GEMINI_URL, success_url_hint="gemini.google.com")

    def generate(
        self, prompt: str, output_path: Optional[Path] = None, count: int = 1
    ) -> list[str]:
        """Generate image(s) from prompt."""
        return asyncio.run(self.generate_async(prompt, output_path, count))

    async def generate_async(
        self,
        prompt: str,
        output_path: Optional[Path] = None,
        count: int = 1,
    ) -> list[str]:
        """Async generate."""
        storage_path = self._get_storage_path()
        if not storage_path.exists():
            raise BrowserGenerationError("No session found. Run: gemini-img login")

        # Default output path
        if not output_path:
            desktop = Path.home() / "Desktop"
            safe = (
                "".join(c for c in prompt[:30] if c.isalnum() or c in " _-")
                .strip()
                .replace(" ", "_")
                or "gemini_image"
            )
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = desktop / f"{safe}_{ts}.png"

        # Launch browser
        browser = BrowserManager(
            storage_path=storage_path,
            headless=self.headless,
        )
        await browser.launch()

        results = []

        try:
            for i in range(count):
                page = await browser.new_page()
                final_path = (
                    output_path
                    if count == 1
                    else Path(output_path).parent
                    / f"{Path(output_path).stem}_{i+1}.png"
                )

                task = Task(id=f"single_{i}", data=prompt, output_path=final_path)
                ctx = Context(task=task, page=page)

                result = await self.handler.execute(ctx)
                await page.close()

                if not result.success:
                    raise BrowserGenerationError(result.error or "Generation failed")

                results.append(final_path)
        finally:
            await browser.close()

        return results
