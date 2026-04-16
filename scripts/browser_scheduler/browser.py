"""Browser lifecycle management for automation tasks."""

from pathlib import Path
from typing import Any, Optional
from playwright._impl._api_structures import ViewportSize


class BrowserManager:
    """
    Manages browser lifecycle with session persistence.

    Usage:
        # For automation tasks
        browser = BrowserManager(
            storage_path=".data/storage.json",
            headless=True
        )
        await browser.launch()
        page = await browser.new_page()
        ...
        await browser.close()

        # For interactive login
        browser.login_sync("https://example.com/login")
    """

    def __init__(
        self,
        storage_path: Path,
        headless: bool = True,
        viewport: Optional[ViewportSize] = None,
        user_agent: Optional[str] = None,
    ):
        self.storage_path = storage_path
        self.headless = headless
        self.viewport = viewport or {"width": 1280, "height": 800}
        self.user_agent = user_agent or (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/131.0.0.0 Safari/537.36"
        )
        self._playwright = None
        self._browser = None
        self._context = None

    async def launch(self) -> None:
        """Launch browser with stored session."""
        from playwright.async_api import async_playwright

        self._playwright = await async_playwright().start()

        self.storage_path.parent.mkdir(parents=True, exist_ok=True)

        storage_state = str(self.storage_path) if self.storage_path.exists() else None

        self._browser = await self._playwright.chromium.launch(headless=self.headless)
        self._context = await self._browser.new_context(
            storage_state=storage_state,
            viewport=self.viewport,
            user_agent=self.user_agent,
            accept_downloads=True,
            locale="zh-CN",
        )

    async def new_page(self) -> Any:
        """Get new page from context."""
        if not self._context:
            raise RuntimeError("Browser not launched. Call launch() first.")
        return await self._context.new_page()

    async def close(self) -> None:
        """Close browser and cleanup."""
        if self._browser:
            await self._browser.close()
            self._browser = None
            self._context = None
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None

    def login_sync(
        self, login_url: str, success_url_hint: Optional[str] = None
    ) -> None:
        """
        Interactive login (sync version).

        Opens headed browser for manual login, then saves session.

        Args:
            login_url: URL to open for login
            success_url_hint: String that should appear in URL after successful login
        """
        from playwright.sync_api import sync_playwright

        self.storage_path.parent.mkdir(parents=True, exist_ok=True)

        # Use persistent context for login
        profile_dir = self.storage_path.parent / "browser-profile"
        profile_dir.mkdir(parents=True, exist_ok=True)

        print(f"Opening browser for login: {login_url}")
        print("1. Complete login in browser")
        print("2. Wait for page to load")
        print("3. Press ENTER here to save session\n")

        with sync_playwright() as p:
            context = p.chromium.launch_persistent_context(
                user_data_dir=str(profile_dir),
                headless=False,
                args=["--disable-blink-features=AutomationControlled"],
            )
            page = context.pages[0] if context.pages else context.new_page()
            page.goto(login_url, wait_until="domcontentloaded", timeout=60000)

            input("[Press ENTER when logged in] ")

            if success_url_hint and success_url_hint not in page.url:
                print(f"Warning: URL doesn't contain '{success_url_hint}': {page.url}")
                if input("Save anyway? [y/N] ").strip().lower() != "y":
                    context.close()
                    return

            context.storage_state(path=str(self.storage_path))
            self.storage_path.chmod(0o600)
            print(f"\nSession saved to: {self.storage_path}")

            context.close()

    @property
    def is_launched(self) -> bool:
        """Check if browser is launched."""
        return self._browser is not None
