import asyncio
import base64
from pathlib import Path
from playwright.async_api import async_playwright, Browser, BrowserContext, Page


class BrowserController:
    def __init__(self, headless: bool = True, video_dir: str | None = None):
        self.headless = headless
        self.video_dir = video_dir
        self._playwright = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self.page: Page | None = None

    async def start(self):
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(headless=self.headless)
        context_options = {"viewport": {"width": 1280, "height": 800}}
        if self.video_dir:
            Path(self.video_dir).mkdir(parents=True, exist_ok=True)
            context_options["record_video_dir"] = self.video_dir
        self._context = await self._browser.new_context(**context_options)
        self.page = await self._context.new_page()

    async def navigate(self, url: str):
        await self.page.goto(url, wait_until="domcontentloaded", timeout=30_000)
        await asyncio.sleep(1)

    async def click(self, selector: str):
        await self.page.click(selector, timeout=10_000)
        await asyncio.sleep(0.5)

    async def type_text(self, selector: str, text: str):
        await self.page.fill(selector, text)
        await asyncio.sleep(0.3)

    async def scroll(self, direction: str = "down", amount: int = 300):
        delta = amount if direction == "down" else -amount
        await self.page.evaluate(f"window.scrollBy(0, {delta})")
        await asyncio.sleep(0.3)

    async def wait(self, ms: int):
        await asyncio.sleep(ms / 1000)

    async def screenshot_bytes(self) -> bytes:
        return await self.page.screenshot(type="png", full_page=False)

    async def screenshot_base64(self) -> str:
        data = await self.screenshot_bytes()
        return base64.standard_b64encode(data).decode()

    async def get_dom_snapshot(self) -> str:
        """Return a trimmed accessibility-tree snapshot for LLM context."""
        try:
            snapshot = await self.page.accessibility.snapshot()
            return self._trim_snapshot(snapshot, depth=4)
        except Exception:
            return ""

    def _trim_snapshot(self, node: dict | None, depth: int) -> str:
        if not node or depth == 0:
            return ""
        role = node.get("role", "")
        name = node.get("name", "")
        value = node.get("value", "")
        line = f"[{role}] {name}"
        if value:
            line += f' = "{value}"'
        children = node.get("children", [])
        child_lines = "\n".join(
            "  " + l
            for child in children
            for l in self._trim_snapshot(child, depth - 1).splitlines()
            if l.strip()
        )
        return f"{line}\n{child_lines}" if child_lines else line

    async def current_url(self) -> str:
        return self.page.url

    async def get_video_path(self) -> str | None:
        if self._context and self.video_dir:
            await self.page.video.path() if self.page.video else None
            return await self.page.video.path() if self.page.video else None
        return None

    async def stop(self) -> str | None:
        video_path = None
        if self.page and self.page.video:
            video_path = await self.page.video.path()
        if self._context:
            await self._context.close()
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()
        return video_path
