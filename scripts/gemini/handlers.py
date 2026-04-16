"""Gemini-specific handlers and store."""

import re
from pathlib import Path
from typing import Optional

from browser_scheduler import (
    Context,
    Handler,
    Result,
    TaskStore,
)

from .config import (
    CHAT_INPUT_SELECTOR,
    DOWNLOAD_BTN_SELECTOR,
    GEMINI_URL,
    IMAGE_ELEMENT_SELECTOR,
    IMAGE_READY_SELECTOR,
    MAKE_IMAGE_CHIP_SEL,
    MORE_MENU_SELECTOR,
    QUALITY_SUFFIX,
    TOOLS_BTN_SEL,
)
from .watermark import remove_gemini_watermark


class GeminiStore(TaskStore):
    """Store for Gemini tasks with prompt scanning."""

    def __init__(self, input_dir: Path, output_dir: Optional[Path] = None):
        super().__init__(
            input_dir=input_dir,
            output_dir=output_dir,
            store_name="gemini_store",
        )


class GeminiHandler(Handler):
    """Handler for Gemini image generation.

    All browser interaction logic lives here. Both GeminiClient and
    GeminiExecutor delegate to this class.
    """

    def __init__(self, quality_suffix: str = QUALITY_SUFFIX, image_timeout: int = 180):
        self.quality_suffix = quality_suffix
        self.image_timeout = image_timeout

    # ── Main execution flow ──────────────────────────────────────────

    async def execute(self, ctx: Context) -> Result:
        """Generate image - full implementation.

        Supports retry: if task.extra["conversation_url"] exists, opens that
        URL directly. If the image is already generated (e.g. previous timeout),
        downloads it without re-submitting.
        """
        task = ctx.task
        page = ctx.page

        try:
            # Navigate — reuse conversation URL on retry, or start fresh
            conversation_url = task.extra.get("conversation_url")
            start_url = conversation_url or GEMINI_URL

            await page.goto(start_url, wait_until="domcontentloaded")
            await page.wait_for_timeout(1500)

            if "accounts.google.com" in page.url:
                return Result(success=False, error="Session expired - run login")

            # On retry with conversation URL: check if image is already ready
            if conversation_url:
                if await self._check_image_ready(page):
                    # Image already generated — just download
                    img_data = await self.download_image(page)
                    if not img_data:
                        return Result(success=False, error="Image ready but download failed")
                    if task.output_path:
                        task.output_path.write_bytes(img_data)
                    return Result(success=True)

            # Fresh task or image not ready yet — need to submit prompt
            input_sel = await self.wait_for_input_box(page)
            if not input_sel:
                return Result(success=False, error="Input box not found after page load")

            if not await self.click_tools_button(page):
                return Result(success=False, error="Failed to click tools button")

            if not await self.click_make_image_chip(page):
                return Result(success=False, error="Failed to click make image chip")

            input_sel = await self.wait_for_input_box(page, timeout=15_000)
            if not input_sel:
                return Result(
                    success=False, error="Input box not found after clicking make image"
                )

            await self.input_and_send(page, input_sel, task.data)

            # Wait for URL to change from /app to /app/{conversation_id}
            try:
                await page.wait_for_url(re.compile(r"/app/[a-f0-9]+$"), timeout=5_000)
            except Exception:
                pass
            task.extra["conversation_url"] = page.url

            if not await self.wait_for_image_ready(page):
                return Result(success=False, error="Image generation timeout")

            img_data = await self.download_image(page)
            if not img_data:
                return Result(success=False, error="Failed to download image")

            if task.output_path:
                task.output_path.write_bytes(img_data)
                # remove_gemini_watermark(task.output_path)

            return Result(success=True)

        except Exception as e:
            return Result(success=False, error=str(e))

    async def _check_image_ready(self, page) -> bool:
        """Quick check if image is already generated on the page."""
        try:
            el = await page.query_selector(IMAGE_READY_SELECTOR)
            return el is not None
        except Exception:
            return False

    # ── Input helpers ─────────────────────────────────────────────────

    async def wait_for_input_box(self, page, timeout: int = 15_000) -> Optional[str]:
        """Wait for input box. Returns working selector or None."""
        selectors = [CHAT_INPUT_SELECTOR, ".ql-editor", 'div[contenteditable="true"]']

        # Quick check — may already be in DOM
        for sel in selectors:
            try:
                if await page.query_selector(sel):
                    return sel
            except Exception:
                continue

        # Wait for first match
        for sel in selectors:
            try:
                if await page.wait_for_selector(sel, timeout=timeout):
                    return sel
            except Exception:
                continue
        return None

    # ── Tools flow ────────────────────────────────────────────────────

    async def click_tools_button(self, page) -> bool:
        """Click the tools button to open the tools drawer."""
        for sel in TOOLS_BTN_SEL.split(","):
            sel = sel.strip()
            if not sel:
                continue
            try:
                btn = await page.query_selector(sel)
                if not btn:
                    btn = await page.wait_for_selector(sel, timeout=5_000)
                if btn:
                    await btn.click()
                    await page.wait_for_timeout(1000)
                    return True
            except Exception:
                continue

        # Fallback: find by text
        try:
            handle = await page.evaluate_handle(
                """() => {
                const btns = Array.from(document.querySelectorAll('button'));
                return btns.find(b => b.textContent && b.textContent.includes('工具'));
            }"""
            )
            el = handle.as_element()
            if el:
                await el.click()
                await page.wait_for_timeout(1000)
                return True
        except Exception:
            pass
        return False

    async def click_make_image_chip(self, page) -> bool:
        """Click the '制作图片' chip in the tools drawer."""
        for sel in MAKE_IMAGE_CHIP_SEL.split(","):
            sel = sel.strip()
            if not sel:
                continue
            try:
                chip = await page.query_selector(sel)
                if not chip:
                    chip = await page.wait_for_selector(sel, timeout=5_000)
                if chip:
                    await chip.click()
                    await page.wait_for_timeout(2000)
                    return True
            except Exception:
                continue

        # Fallback: find by text
        try:
            handle = await page.evaluate_handle(
                """() => {
                const btns = Array.from(document.querySelectorAll('button'));
                return btns.find(b => b.textContent && b.textContent.includes('制作图片'));
            }"""
            )
            el = handle.as_element()
            if el:
                await el.click()
                await page.wait_for_timeout(2000)
                return True
        except Exception:
            pass
        return False

    # ── Prompt & send ─────────────────────────────────────────────────

    def _enhance_prompt(self, prompt: str) -> str:
        """Add quality suffix if needed."""
        if (
            "ultra sharp" not in prompt.lower()
            and "high definition" not in prompt.lower()
        ):
            return prompt + self.quality_suffix
        return prompt

    async def input_and_send(self, page, selector: str, prompt: str) -> None:
        """Insert prompt text and send with Enter.

        Uses Playwright's keyboard.type() which fires real keyboard events
        (keydown → input → keyup) so Gemini's framework always detects the
        content change. Falls back to type() per character if needed.
        """
        enhanced = self._enhance_prompt(prompt)

        # Click to focus the input
        input_box = await page.wait_for_selector(selector, timeout=5_000)
        await input_box.click()
        await page.wait_for_timeout(100)

        # Use keyboard.type() — fires real keyboard events that Gemini detects
        # For newlines: press Enter creates a new paragraph in the editor,
        # but would also submit. Instead, use Shift+Enter which inserts a
        # line break without submitting.
        lines = enhanced.split("\n")
        for i, line in enumerate(lines):
            if line:
                await page.keyboard.type(line, delay=5)
            # Insert line break (not submit) between lines
            if i < len(lines) - 1:
                await page.keyboard.press("Shift+Enter")

        # Send message
        await page.keyboard.press("Enter")

    # ── Image generation & download ───────────────────────────────────

    async def wait_for_image_ready(self, page) -> bool:
        """Wait for image generation to complete."""
        selectors = (
            IMAGE_READY_SELECTOR,
            'button[aria-label*="下载完整"]',
            'button[aria-label*="Download full"]',
        )
        for sel in selectors:
            try:
                await page.wait_for_selector(sel, timeout=self.image_timeout * 1000)
                return True
            except Exception:
                continue
        return False

    async def download_image(self, page) -> Optional[bytes]:
        """Download the full-size generated image.

        Strategy 1: Click the direct download button that appears after generation.
        Strategy 2: Click more menu → download (for older UI or different states).
        Uses Playwright's expect_download to capture the real file.
        """
        try:
            await page.wait_for_selector(IMAGE_ELEMENT_SELECTOR, timeout=20_000)
        except Exception:
            pass

        # Strategy 1: Direct download button
        try:
            dl_btn = await page.wait_for_selector(
                'button[data-test-id="download-generated-image-button"]',
                timeout=5_000,
            )
            if dl_btn:
                async with page.expect_download(timeout=30_000) as download_info:
                    await dl_btn.click()
                download = await download_info.value
                tmp_path = await download.path()
                if tmp_path and tmp_path.exists():
                    return tmp_path.read_bytes()
        except Exception:
            pass

        # Strategy 2: More menu → Download
        try:
            async with page.expect_download(timeout=30_000) as download_info:
                # Find the more menu button scoped to image area
                # Avoid conversation-actions-menu at the top of the page
                more_btn = await page.wait_for_selector(
                    'button[data-test-id="more-menu-button"]',
                    timeout=5_000,
                )
                await more_btn.click()
                await page.wait_for_timeout(500)

                dl_btn = await page.wait_for_selector(
                    DOWNLOAD_BTN_SELECTOR, timeout=5_000
                )
                await dl_btn.click()

            download = await download_info.value
            tmp_path = await download.path()
            if tmp_path and tmp_path.exists():
                return tmp_path.read_bytes()
        except Exception:
            pass

        # Fallback: canvas export (lossy, smaller than original)
        return await self._canvas_fallback(page)

    # ── Private download helpers ──────────────────────────────────────

    async def _canvas_fallback(self, page) -> Optional[bytes]:
        """Extract image via canvas export."""
        import base64

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
        return None
