"""
OOP wrapper around the Gemini headless-browser image generator.

Typical usage::

    gen = GeminiImageGenerator()
    gen.login()                           # once — saves cookies
    paths = gen.generate("a red cat", count=2)
"""

import asyncio
import base64
import sys
from datetime import datetime
from pathlib import Path

from .config import (
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


class BrowserGenerationError(Exception):
    """Raised when browser-based image generation fails."""

    def __init__(self, message: str, retryable: bool = True) -> None:
        super().__init__(message)
        self.retryable = retryable


def _fix_windows_event_loop() -> None:
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.DefaultEventLoopPolicy())


class GeminiImageGenerator:
    """Headless-browser Gemini image generator."""

    def __init__(
        self,
        skill_dir: Path | None = None,
        headless: bool = True,
    ) -> None:
        # Default skill_dir = two levels above this file (scripts/gemini/ → skill root)
        self.skill_dir = skill_dir or Path(__file__).parent.parent.parent
        self.storage_path = self.skill_dir / ".data" / "storage_state.json"
        self.profile_dir = self.skill_dir / ".data" / "browser-profile"
        self.download_dir = self.skill_dir / ".data" / "downloads"
        self.headless = headless
        self.download_dir.mkdir(parents=True, exist_ok=True)

    # ── helpers ────────────────────────────────────────────────────────────────

    def _log(self, msg: str) -> None:
        print(f"[gemini-img] {msg}", file=sys.stderr)

    @staticmethod
    def default_output(prompt: str) -> str:
        """Return a timestamped PNG path on the desktop."""
        desktop = Path.home() / "Desktop"
        safe = "".join(c for c in prompt[:30] if c.isalnum() or c in " _-").strip()
        safe = safe.replace(" ", "_") or "gemini_image"
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        return str(desktop / f"{safe}_{ts}.png")

    def _enhance_prompt(self, prompt: str) -> str:
        if (
            "ultra sharp" not in prompt.lower()
            and "high definition" not in prompt.lower()
        ):
            return prompt + QUALITY_SUFFIX
        return prompt

    @staticmethod
    def _resolve_output_path(output_path: str, count: int, index: int) -> str:
        if count == 1:
            return output_path
        obj = Path(output_path)
        return str(obj.parent / f"{obj.stem}_{index + 1}{obj.suffix}")

    # ── login ──────────────────────────────────────────────────────────────────

    def login(self) -> None:
        """Open a headed browser for manual Google login; persist cookies."""
        _fix_windows_event_loop()

        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            self._log(
                "Playwright not found. "
                "Run: pip install playwright && playwright install chromium"
            )
            raise SystemExit(1)

        self.profile_dir.mkdir(parents=True, exist_ok=True)
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)

        print("[gemini-img] Opening browser for Google login...")
        print("[gemini-img] Steps:")
        print("  1. Complete Google login in the browser window")
        print("  2. Wait until Gemini homepage loads fully")
        print("  3. Press ENTER here to save and close\n")

        with sync_playwright() as p:
            context = p.chromium.launch_persistent_context(
                user_data_dir=str(self.profile_dir),
                headless=False,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--password-store=basic",
                ],
                ignore_default_args=["--enable-automation"],
            )

            page = context.pages[0] if context.pages else context.new_page()
            page.goto(GEMINI_URL, wait_until="domcontentloaded", timeout=60_000)

            input("[Press ENTER when you have logged in and see the Gemini homepage] ")

            if "gemini.google.com" not in page.url:
                self._log(f"Warning: current URL is {page.url}")
                if input("Save anyway? [y/N] ").strip().lower() != "y":
                    context.close()
                    raise SystemExit(1)

            context.storage_state(path=str(self.storage_path))
            self.storage_path.chmod(0o600)
            context.close()

        print(f"\n[gemini-img] Session saved to: {self.storage_path}")
        print("[gemini-img] Login complete. You won't need to log in again.")

    # ── public generate API ────────────────────────────────────────────────────

    def generate(
        self,
        prompt: str,
        output_path: str | None = None,
        count: int = 1,
    ) -> list[str]:
        """Synchronous wrapper; returns list of saved file paths.

        Raises:
            BrowserGenerationError: if generation fails.
        """
        _fix_windows_event_loop()
        return asyncio.run(
            self.generate_async(
                prompt,
                output_path or self.default_output(prompt),
                count,
            )
        )

    async def generate_async(
        self,
        prompt: str,
        output_path: str | None = None,
        count: int = 1,
    ) -> list[str]:
        """Async core — generate *count* images; return list of saved paths.

        Raises:
            BrowserGenerationError: if generation fails (retryable flag indicates
                whether a retry might succeed).
        """
        from playwright.async_api import async_playwright

        if not self.storage_path.exists():
            raise BrowserGenerationError(
                "No saved session found. Run: gemini-img login",
                retryable=False,
            )

        output_path = output_path or self.default_output(prompt)
        enhanced = self._enhance_prompt(prompt)
        results: list[str] = []

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=self.headless)
            context = await browser.new_context(
                storage_state=str(self.storage_path),
                viewport={"width": 1280, "height": 800},
                accept_downloads=True,
                locale="zh-CN",
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/131.0.0.0 Safari/537.36"
                ),
            )
            page = None
            try:
                page = await context.new_page()
                self._log(f"Opening Gemini... (headless={self.headless})")
                await page.goto(GEMINI_URL, wait_until="domcontentloaded")
                await page.wait_for_timeout(2500)

                if "accounts.google.com" in page.url:
                    raise BrowserGenerationError(
                        "Session expired — run: gemini-img login",
                        retryable=False,
                    )

                self._log("Gemini loaded.")

                for i in range(count):
                    self._log(f"Generating image {i + 1}/{count}...")
                    final = self._resolve_output_path(output_path, count, i)
                    await self._generate_one(page, enhanced, final)
                    results.append(final)

                    if i < count - 1:
                        await page.wait_for_timeout(1500)

            except BrowserGenerationError:
                if page:
                    try:
                        dbg = str(self.skill_dir / "debug_screenshot.png")
                        await page.screenshot(path=dbg)
                        self._log(f"Debug screenshot: {dbg}")
                    except Exception:
                        pass
                await browser.close()
                raise
            except Exception as e:
                self._log(f"Error: {e}")
                if page:
                    try:
                        dbg = str(self.skill_dir / "debug_screenshot.png")
                        await page.screenshot(path=dbg)
                        self._log(f"Debug screenshot: {dbg}")
                    except Exception:
                        pass
                await browser.close()
                raise BrowserGenerationError(str(e), retryable=True) from e

            await browser.close()

        return results

    # ── private browser interaction helpers ───────────────────────────────────

    async def _click_tools_button(self, page) -> bool:
        """Click the 工具 button to open the tools panel; return True on success."""
        try:
            btn = await page.wait_for_selector(TOOLS_BTN_SEL, timeout=15_000)
            await btn.click()
            self._log("Clicked 工具 button")
            return True
        except Exception:
            pass

        handle = await page.evaluate_handle(
            """() => {
            const btns = Array.from(document.querySelectorAll('button'));
            return btns.find(b => b.innerText && b.innerText.trim().includes('工具'));
        }"""
        )
        try:
            el = handle.as_element()
            if el:
                await el.click()
                self._log("Clicked 工具 button (text fallback)")
                return True
        except Exception:
            pass

        self._log("工具 button not found, waiting 15s...")
        await page.wait_for_timeout(15_000)
        try:
            btn = await page.wait_for_selector(TOOLS_BTN_SEL, timeout=5_000)
            await btn.click()
            self._log("Clicked 工具 button (delayed)")
            return True
        except Exception:
            self._log("工具 button still not found, proceeding without it")
            return False

    async def _click_make_image_chip(self, page) -> bool:
        """Click the 制作图片 chip inside the tools panel; return True on success."""
        await page.wait_for_timeout(600)

        try:
            chip = await page.wait_for_selector(MAKE_IMAGE_CHIP_SEL, timeout=8_000)
            await chip.click()
            self._log("Clicked 制作图片 chip")
            return True
        except Exception:
            pass

        handle = await page.evaluate_handle(
            """() => {
            const btns = Array.from(document.querySelectorAll('button'));
            return btns.find(b => b.innerText && b.innerText.trim().includes('制作图片'));
        }"""
        )
        try:
            el = handle.as_element()
            if el:
                await el.click()
                self._log("Clicked 制作图片 chip (text fallback)")
                return True
        except Exception:
            pass

        self._log("制作图片 chip not found")
        return False

    async def _wait_for_image_ready(self, page) -> None:
        """Block until Gemini signals image generation is complete (up to 180s)."""
        selectors = (
            IMAGE_READY_SELECTOR,
            'button[aria-label*="下载完整"]',
            'button[aria-label*="Download full"]',
        )
        for sel in selectors:
            try:
                await page.wait_for_selector(sel, timeout=180_000)
                self._log(f"Image ready (detected via: {sel})")
                return
            except Exception:
                continue

        raise BrowserGenerationError(
            "Image not ready after 180s",
            retryable=True,
        )

    async def _intercept_fullsize_image(self, page) -> bytes | None:
        """Click 更多 → 下载图片; intercept the full-size network response."""
        fullsize_images: list[tuple[str, bytes]] = []

        async def _on_response(response):
            ct = response.headers.get("content-type", "")
            if any(t in ct for t in ("image/jpeg", "image/png", "image/webp")):
                try:
                    body = await response.body()
                    if len(body) >= 200_000:
                        fullsize_images.append((response.url, body))
                        self._log(
                            f"Full-size captured: {len(body) // 1024}KB  {response.url[:80]}"
                        )
                except Exception:
                    pass

        page.on("response", _on_response)
        try:
            more_btn = await page.wait_for_selector(MORE_MENU_SELECTOR, timeout=10_000)
            await more_btn.click()
            self._log("Clicked 更多 menu button")
            await page.wait_for_timeout(500)

            dl_btn = await page.wait_for_selector(DOWNLOAD_BTN_SELECTOR, timeout=10_000)
            await dl_btn.click()
            self._log("Clicked 下载图片 button, waiting for full-size response...")

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

    async def _canvas_fallback(self, page) -> bytes:
        """Extract image via canvas export when network intercept yields nothing."""
        b64 = await page.evaluate(
            f"""async () => {{
            const img = document.querySelector('{IMAGE_ELEMENT_SELECTOR}');
            if (!img) return null;
            try {{
                const c = document.createElement('canvas');
                c.width = img.naturalWidth; c.height = img.naturalHeight;
                c.getContext('2d').drawImage(img, 0, 0);
                return c.toDataURL('image/jpeg', 0.95).split(',')[1];
            }} catch(e) {{}}
            try {{
                const r = await fetch(img.src);
                const buf = await r.arrayBuffer();
                return btoa(String.fromCharCode(...new Uint8Array(buf)));
            }} catch(e) {{}}
            return null;
        }}"""
        )
        if not b64:
            raise BrowserGenerationError(
                "Could not export image (canvas fallback failed)",
                retryable=True,
            )
        return base64.b64decode(b64)

    async def _generate_one(self, page, enhanced_prompt: str, output_path: str) -> None:
        """Submit one prompt, download the result, and remove the watermark."""
        input_box = await page.wait_for_selector(
            'div[contenteditable="true"][role="textbox"]',
            timeout=30_000,
        )

        if await self._click_tools_button(page):
            if await self._click_make_image_chip(page):
                input_box = await page.wait_for_selector(
                    'div[contenteditable="true"][role="textbox"]',
                    timeout=10_000,
                )

        await input_box.click()
        await page.keyboard.press("Control+a")
        await page.keyboard.press("Backspace")
        await page.wait_for_timeout(200)

        self._log(f"Prompt: {enhanced_prompt[:80]}...")
        await page.keyboard.type(enhanced_prompt, delay=15)
        await page.wait_for_timeout(400)
        await page.keyboard.press("Enter")

        self._log("Prompt submitted. Waiting for image (up to 180s)...")
        await self._wait_for_image_ready(page)

        try:
            await page.wait_for_selector(IMAGE_ELEMENT_SELECTOR, timeout=20_000)
            self._log("Image element rendered.")
        except Exception:
            pass
        await page.wait_for_timeout(500)

        img_data = await self._intercept_fullsize_image(page)
        if img_data:
            Path(output_path).write_bytes(img_data)
            self._log(
                f"Saved full-size from network: {output_path}  ({len(img_data) // 1024} KB)"
            )
        else:
            self._log("No full-size network image captured; trying canvas export...")
            img_data = await self._canvas_fallback(page)
            Path(output_path).write_bytes(img_data)
            self._log(f"Saved from canvas: {output_path}")

        remove_gemini_watermark(output_path)
