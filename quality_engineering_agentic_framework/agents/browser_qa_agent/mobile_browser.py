"""
Mobile browser controllers:
  - MobileWebBrowser: Playwright with device emulation (mobile web)
  - NativeMobileBrowser: Appium (native iOS / Android apps)
"""
import asyncio
import base64
from pathlib import Path
from playwright.async_api import async_playwright, Browser, BrowserContext, Page


# Common device presets (Playwright built-ins)
DEVICE_PRESETS = {
    "iphone_14": "iPhone 14",
    "iphone_14_pro": "iPhone 14 Pro",
    "iphone_se": "iPhone SE",
    "pixel_7": "Pixel 7",
    "galaxy_s23": "Galaxy S23",
    "ipad_pro": "iPad Pro 11",
    "ipad_mini": "iPad Mini",
}


class MobileWebBrowser:
    """Playwright browser emulating a mobile device (mobile web)."""

    def __init__(
        self,
        device: str = "iphone_14",
        headless: bool = True,
        video_dir: str | None = None,
    ):
        self.device_name = DEVICE_PRESETS.get(device, device)
        self.headless = headless
        self.video_dir = video_dir
        self._playwright = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self.page: Page | None = None

    async def start(self):
        self._playwright = await async_playwright().start()
        device_config = self._playwright.devices.get(self.device_name, {})
        self._browser = await self._playwright.chromium.launch(headless=self.headless)
        context_options = {**device_config}
        if self.video_dir:
            Path(self.video_dir).mkdir(parents=True, exist_ok=True)
            context_options["record_video_dir"] = self.video_dir
        self._context = await self._browser.new_context(**context_options)
        self.page = await self._context.new_page()

    async def navigate(self, url: str):
        await self.page.goto(url, wait_until="domcontentloaded", timeout=30_000)
        await asyncio.sleep(1)

    async def click(self, selector: str):
        await self.page.tap(selector, timeout=10_000)  # tap instead of click for mobile
        await asyncio.sleep(0.5)

    async def tap(self, selector: str):
        await self.page.tap(selector, timeout=10_000)
        await asyncio.sleep(0.5)

    async def type_text(self, selector: str, text: str):
        await self.page.fill(selector, text)
        await asyncio.sleep(0.3)

    async def swipe(self, direction: str = "up", element: str | None = None):
        """Simulate swipe via touch events."""
        if element:
            el = self.page.locator(element).first
            box = await el.bounding_box()
            cx, cy = (box["x"] + box["width"] / 2, box["y"] + box["height"] / 2) if box else (200, 400)
        else:
            size = self.page.viewport_size or {"width": 390, "height": 844}
            cx, cy = size["width"] / 2, size["height"] / 2

        deltas = {"up": (0, -200), "down": (0, 200), "left": (-200, 0), "right": (200, 0)}
        dx, dy = deltas.get(direction, (0, -200))

        await self.page.evaluate(f"""
            (() => {{
                const el = document.elementFromPoint({cx}, {cy});
                const ts = (x, y) => new Touch({{identifier: 1, target: el, clientX: x, clientY: y, pageX: x, pageY: y}});
                el.dispatchEvent(new TouchEvent('touchstart', {{touches: [ts({cx}, {cy})], bubbles: true}}));
                el.dispatchEvent(new TouchEvent('touchend', {{changedTouches: [ts({cx + dx}, {cy + dy})], bubbles: true}}));
            }})()
        """)
        await asyncio.sleep(0.5)

    async def scroll(self, direction: str = "down", amount: int = 300):
        delta = amount if direction == "down" else -amount
        await self.page.evaluate(f"window.scrollBy(0, {delta})")
        await asyncio.sleep(0.3)

    async def wait(self, ms: int):
        await asyncio.sleep(ms / 1000)

    async def screenshot_bytes(self) -> bytes:
        return await self.page.screenshot(type="png")

    async def screenshot_base64(self) -> str:
        return base64.standard_b64encode(await self.screenshot_bytes()).decode()

    async def get_dom_snapshot(self) -> str:
        try:
            snapshot = await self.page.accessibility.snapshot()
            return _trim_snapshot(snapshot, depth=4)
        except Exception:
            return ""

    async def current_url(self) -> str:
        return self.page.url

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


class NativeMobileBrowser:
    """
    Appium-based controller for native iOS and Android apps.
    Requires Appium server running and a real/virtual device connected.
    """

    def __init__(self, desired_caps: dict, appium_url: str = "http://localhost:4723"):
        self.desired_caps = desired_caps
        self.appium_url = appium_url
        self._driver = None

    def start(self):
        try:
            from appium import webdriver as appium_webdriver
            from appium.options import AppiumOptions
        except ImportError:
            raise ImportError("Install Appium Python client: pip install Appium-Python-Client")

        options = AppiumOptions()
        options.load_capabilities(self.desired_caps)
        self._driver = appium_webdriver.Remote(self.appium_url, options=options)

    def navigate(self, url: str):
        if hasattr(self._driver, "get"):
            self._driver.get(url)

    def tap(self, selector: str):
        from appium.webdriver.common.appiumby import AppiumBy
        # selector can be: "~accessibility_id", "#resource_id", or ".class_name"
        by, value = self._parse_selector(selector)
        self._driver.find_element(by, value).click()

    def click(self, selector: str):
        self.tap(selector)

    def type_text(self, selector: str, text: str):
        from appium.webdriver.common.appiumby import AppiumBy
        by, value = self._parse_selector(selector)
        el = self._driver.find_element(by, value)
        el.clear()
        el.send_keys(text)

    def swipe(self, direction: str = "up", element: str | None = None):
        size = self._driver.get_window_size()
        w, h = size["width"], size["height"]
        cx = w // 2
        swipes = {
            "up": (cx, int(h * 0.7), cx, int(h * 0.3)),
            "down": (cx, int(h * 0.3), cx, int(h * 0.7)),
            "left": (int(w * 0.8), h // 2, int(w * 0.2), h // 2),
            "right": (int(w * 0.2), h // 2, int(w * 0.8), h // 2),
        }
        x1, y1, x2, y2 = swipes.get(direction, swipes["up"])
        self._driver.swipe(x1, y1, x2, y2, duration=500)

    def scroll(self, direction: str = "down", amount: int = 300):
        self.swipe(direction)

    def wait(self, ms: int):
        import time
        time.sleep(ms / 1000)

    def screenshot_bytes(self) -> bytes:
        return self._driver.get_screenshot_as_png()

    def screenshot_base64(self) -> str:
        return self._driver.get_screenshot_as_base64()

    def get_dom_snapshot(self) -> str:
        try:
            src = self._driver.page_source
            return src[:3000]
        except Exception:
            return ""

    def current_url(self) -> str:
        try:
            return self._driver.current_url
        except Exception:
            return self.desired_caps.get("app", "native")

    def stop(self) -> str | None:
        if self._driver:
            self._driver.quit()
        return None

    def _parse_selector(self, selector: str):
        from appium.webdriver.common.appiumby import AppiumBy
        if selector.startswith("~"):
            return AppiumBy.ACCESSIBILITY_ID, selector[1:]
        elif selector.startswith("#"):
            return AppiumBy.ID, selector[1:]
        elif selector.startswith("//") or selector.startswith("(//"):
            return AppiumBy.XPATH, selector
        else:
            return AppiumBy.XPATH, f"//*[@text='{selector}']"


def _trim_snapshot(node: dict | None, depth: int) -> str:
    if not node or depth == 0:
        return ""
    role = node.get("role", "")
    name = node.get("name", "")
    line = f"[{role}] {name}"
    children = node.get("children", [])
    child_lines = "\n".join(
        "  " + l
        for child in children
        for l in _trim_snapshot(child, depth - 1).splitlines()
        if l.strip()
    )
    return f"{line}\n{child_lines}" if child_lines else line
