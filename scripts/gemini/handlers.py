"""Gemini-specific handlers and store."""

from pathlib import Path
from typing import Optional

from browser_scheduler import (
    Context,
    Handler,
    Result,
    TaskStore,
    insert_text_with_newlines,
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

    Contains all browser interaction logic. Both GeminiClient and
    GeminiExecutor should delegate browser operations to this class
    to avoid duplicating selector/interaction knowledge.
    """

    def __init__(self, quality_suffix: str = QUALITY_SUFFIX, image_timeout: int = 180):
        self.quality_suffix = quality_suffix
        self.image_timeout = image_timeout

    def _enhance_prompt(self, prompt: str) -> str:
        """Add quality suffix if needed."""
        if (
            "ultra sharp" not in prompt.lower()
            and "high definition" not in prompt.lower()
        ):
            return prompt + self.quality_suffix
        return prompt

    # ── Browser interaction helpers ──────────────────────────────────

    async def wait_for_input_box(self, page, timeout: int = 15_000) -> Optional[str]:
        """Wait for any known input box selector to appear on the page.

        Uses page.query_selector for instant check first, then falls back
        to wait_for_selector with the first candidate.
        Returns the working selector string, or None if not found.
        """
        selectors = [
            CHAT_INPUT_SELECTOR,
            '.ql-editor',
            'div[contenteditable="true"]',
        ]
        # Quick check — element may already be in DOM
        for sel in selectors:
            try:
                if await page.query_selector(sel):
                    return sel
            except Exception:
                continue

        # Wait for the most specific selector first
        for sel in selectors:
            try:
                el = await page.wait_for_selector(sel, timeout=timeout)
                if el:
                    return sel
            except Exception:
                continue
        return None

    async def click_tools_button(self, page) -> bool:
        """Click the tools button to open the tools drawer."""
        for sel in TOOLS_BTN_SEL.split(','):
            sel = sel.strip()
            if not sel:
                continue
            try:
                # Quick check first
                btn = await page.query_selector(sel)
                if not btn:
                    btn = await page.wait_for_selector(sel, timeout=5_000)
                if btn:
                    await btn.click()
                    await page.wait_for_timeout(2000)
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
                await page.wait_for_timeout(2000)
                return True
        except Exception:
            pass
        return False

    async def click_make_image_chip(self, page) -> bool:
        """Click the '制作图片' chip in the tools drawer."""
        await page.wait_for_timeout(2000)
        for sel in MAKE_IMAGE_CHIP_SEL.split(','):
            sel = sel.strip()
            if not sel:
                continue
            try:
                chip = await page.query_selector(sel)
                if not chip:
                    chip = await page.wait_for_selector(sel, timeout=5_000)
                if chip:
                    await chip.click()
                    await page.wait_for_timeout(3000)
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
                await page.wait_for_timeout(3000)
                return True
        except Exception:
            pass
        return False

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
        """Download the generated image."""
        # Wait for image element to render
        try:
            await page.wait_for_selector(IMAGE_ELEMENT_SELECTOR, timeout=20_000)
        except Exception:
            pass
        await page.wait_for_timeout(500)

        # Try network intercept first
        img_data = await self._intercept_fullsize_image(page)
        if img_data:
            return img_data

        # Fallback to canvas export
        return await self._canvas_fallback(page)

    # ── Private download helpers ─────────────────────────────────────

    async def _intercept_fullsize_image(self, page) -> Optional[bytes]:
        """Intercept full-size image from network."""
        fullsize_images = []

        async def _on_response(response):
            ct = response.headers.get("content-type", "")
            if any(t in ct for t in ("image/jpeg", "image/png", "image/webp")):
                try:
                    body = await response.body()
                    if len(body) >= 200_000:
                        fullsize_images.append((response.url, body))
                except Exception:
                    pass

        page.on("response", _on_response)
        try:
            more_btn = await page.wait_for_selector(MORE_MENU_SELECTOR, timeout=10_000)
            await more_btn.click()
            await page.wait_for_timeout(500)

            dl_btn = await page.wait_for_selector(DOWNLOAD_BTN_SELECTOR, timeout=10_000)
            await dl_btn.click()

            for _ in range(60):
                if fullsize_images:
                    break
                await page.wait_for_timeout(500)
        finally:
            page.remove_listener("response", _on_response)

        if fullsize_images:
            _, body = max(fullsize_images, key=lambda x: len(x[1]))
            return body
        return None

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

    # ── Main execution flow ──────────────────────────────────────────

    async def execute(self, ctx: Context) -> Result:
        """Generate image - full implementation."""
        task = ctx.task
        page = ctx.page

        try:
            # Navigate — use domcontentloaded + selector wait instead of networkidle
            # (Gemini keeps WebSocket connections open, so networkidle always times out)
            await page.goto(GEMINI_URL, wait_until="domcontentloaded")
            await page.wait_for_timeout(2000)

            # Check session (after short wait for possible redirects)
            if "accounts.google.com" in page.url:
                return Result(success=False, error="Session expired - run login")

            # Wait for the initial input box (proves the page is ready)
            input_sel = await self.wait_for_input_box(page)
            if not input_sel:
                return Result(success=False, error="Input box not found after page load")

            # Click tools button → make image chip
            if not await self.click_tools_button(page):
                # Retry once after a longer wait
                await page.wait_for_timeout(10_000)
                if not await self.click_tools_button(page):
                    return Result(success=False, error="Failed to click tools button")

            if not await self.click_make_image_chip(page):
                return Result(success=False, error="Failed to click make image chip")

            # Wait for the image-generation input box to appear
            input_sel = await self.wait_for_input_box(page, timeout=15_000)
            if not input_sel:
                return Result(success=False, error="Input box not found after clicking make image")

            # Focus the input box before inserting text
            input_box = await page.wait_for_selector(input_sel, timeout=5_000)
            await input_box.click()
            await page.wait_for_timeout(200)

            # Insert prompt text
            enhanced = self._enhance_prompt(task.data)
            await insert_text_with_newlines(page, input_sel, enhanced)
            await page.wait_for_timeout(400)
            await page.keyboard.press("Enter")

            # Wait for image generation
            if not await self.wait_for_image_ready(page):
                return Result(success=False, error="Image generation timeout")

            # Download image
            img_data = await self.download_image(page)
            if not img_data:
                return Result(success=False, error="Failed to download image")

            # Save image
            if task.output_path:
                task.output_path.write_bytes(img_data)
                remove_gemini_watermark(task.output_path)

            return Result(success=True)

        except Exception as e:
            return Result(success=False, error=str(e))
