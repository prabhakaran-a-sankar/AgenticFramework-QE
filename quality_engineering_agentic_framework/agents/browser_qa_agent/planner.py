import asyncio
import tempfile
from dataclasses import dataclass, field
from .browser import BrowserController
from .mobile_browser import MobileWebBrowser, NativeMobileBrowser
from .providers import AgentAction
from .executor import ActionExecutor, StepTrace
from .storage import ArtifactStorage

# Platform constants
PLATFORM_WEB = "web"
PLATFORM_MOBILE_WEB = "mobile_web"
PLATFORM_MOBILE_NATIVE = "mobile_native"


@dataclass
class PlannerResult:
    status: str  # passed | failed | error
    summary: str
    traces: list[StepTrace] = field(default_factory=list)
    findings: list[dict] = field(default_factory=list)
    video_path: str | None = None


class QAPlanner:
    """
    Orchestrates the agentic test loop across web and mobile platforms.

    platform options:
      - "web"              — Desktop Playwright browser
      - "mobile_web"       — Playwright with mobile device emulation
      - "mobile_native"    — Appium (native iOS / Android)

    mobile_config (for mobile_web):
      {"device": "iphone_14"}  # any DEVICE_PRESETS key or Playwright device name

    appium_config (for mobile_native):
      {"desired_caps": {...}, "appium_url": "http://localhost:4723"}
    """

    def __init__(
        self,
        llm,
        storage: ArtifactStorage,
        platform: str = PLATFORM_WEB,
        max_steps: int = 30,
        headless: bool = True,
        mobile_config: dict | None = None,
        appium_config: dict | None = None,
    ):
        self.llm = llm
        self.storage = storage
        self.platform = platform
        self.max_steps = max_steps
        self.headless = headless
        self.mobile_config = mobile_config or {}
        self.appium_config = appium_config or {}

    def _make_browser(self, video_dir: str):
        if self.platform == PLATFORM_MOBILE_WEB:
            device = self.mobile_config.get("device", "iphone_14")
            return MobileWebBrowser(device=device, headless=self.headless, video_dir=video_dir)
        elif self.platform == PLATFORM_MOBILE_NATIVE:
            return NativeMobileBrowser(
                desired_caps=self.appium_config.get("desired_caps", {}),
                appium_url=self.appium_config.get("appium_url", "http://localhost:4723"),
            )
        else:
            return BrowserController(headless=self.headless, video_dir=video_dir)

    async def run(self, run_id: str, base_url: str, nl_description: str) -> PlannerResult:
        video_dir = tempfile.mkdtemp(prefix=f"qa_video_{run_id}_")
        browser = self._make_browser(video_dir)
        is_native = self.platform == PLATFORM_MOBILE_NATIVE

        # Native Appium is sync; web/mobile_web are async
        if is_native:
            browser.start()
        else:
            await browser.start()

        executor = ActionExecutor(browser, is_async=not is_native)
        traces: list[StepTrace] = []
        findings: list[dict] = []
        history: list[dict] = []
        final_status = "passed"
        final_summary = ""

        try:
            if is_native:
                browser.navigate(base_url)
            else:
                await browser.navigate(base_url)

            for step in range(self.max_steps):
                if is_native:
                    screenshot_b64 = browser.screenshot_base64()
                    dom_snapshot = browser.get_dom_snapshot()
                    current_url = browser.current_url()
                else:
                    screenshot_b64 = await browser.screenshot_base64()
                    dom_snapshot = await browser.get_dom_snapshot()
                    current_url = await browser.current_url()

                action = self.llm.next_action(
                    test_goal=nl_description,
                    screenshot_b64=screenshot_b64,
                    dom_snapshot=dom_snapshot,
                    history=history,
                    current_url=current_url,
                    platform=self.platform,
                )

                if action.tool_name == "done":
                    final_status = action.tool_input.get("status", "passed")
                    final_summary = action.tool_input.get("summary", "")
                    break

                if is_native:
                    trace = executor.execute_sync(action, step)
                else:
                    trace = await executor.execute(action, step)

                if trace.screenshot_b64:
                    key = f"runs/{run_id}/steps/step_{step:03d}.png"
                    import base64
                    data = base64.standard_b64decode(trace.screenshot_b64)
                    url = await self.storage.upload(key, data, "image/png")
                    trace.screenshot_url = url
                    if trace.finding:
                        trace.finding["screenshot_url"] = url

                traces.append(trace)
                if trace.finding:
                    findings.append(trace.finding)

                history.append({
                    "user": f"Step {step}: executed {action.tool_name}",
                    "assistant": f"Action {action.tool_name} done. Bug found: {bool(trace.finding)}",
                })
                if len(history) > 20:
                    history = history[-20:]

        except Exception as e:
            final_status = "error"
            final_summary = f"Agent loop error: {e}"
        finally:
            if is_native:
                video_path = browser.stop()
            else:
                video_path = await browser.stop()

        if findings:
            final_status = "failed"

        return PlannerResult(
            status=final_status,
            summary=final_summary or f"Completed {len(traces)} steps. Bugs: {len(findings)}",
            traces=traces,
            findings=findings,
            video_path=video_path,
        )
