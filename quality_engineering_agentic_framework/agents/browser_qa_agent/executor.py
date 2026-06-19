from dataclasses import dataclass, field
from .providers import AgentAction


@dataclass
class StepTrace:
    step: int
    action: str
    action_input: dict
    screenshot_b64: str = ""
    screenshot_url: str = ""
    url: str = ""
    assertion_passed: bool | None = None
    finding: dict | None = None


class ActionExecutor:
    """
    Executes agent actions on a browser (web/mobile_web async or mobile_native sync).
    Pass is_async=False for Appium (NativeMobileBrowser).
    """

    def __init__(self, browser, is_async: bool = True):
        self.browser = browser
        self.is_async = is_async

    # ── Async path (Playwright web / mobile_web) ─────────────────────────────

    async def execute(self, action: AgentAction, step: int) -> StepTrace:
        trace = StepTrace(step=step, action=action.tool_name, action_input=action.tool_input)
        try:
            await self._dispatch_async(action)
            if action.tool_name not in ("done",):
                trace.screenshot_b64 = await self.browser.screenshot_base64()
                trace.url = await self.browser.current_url()
        except Exception as e:
            trace = self._record_error(trace, action, e)
            try:
                trace.screenshot_b64 = await self.browser.screenshot_base64()
            except Exception:
                pass
        return self._apply_assertion(trace, action)

    async def _dispatch_async(self, action: AgentAction):
        n, inp = action.tool_name, action.tool_input
        if n == "navigate":
            await self.browser.navigate(inp["url"])
        elif n == "click":
            await self.browser.click(inp["selector"])
        elif n == "tap":
            await self.browser.tap(inp["selector"])
        elif n == "type_text":
            await self.browser.type_text(inp["selector"], inp["text"])
        elif n == "scroll":
            await self.browser.scroll(inp.get("direction", "down"), inp.get("amount", 300))
        elif n == "swipe":
            await self.browser.swipe(inp.get("direction", "up"), inp.get("element"))
        elif n == "wait":
            await self.browser.wait(inp.get("ms", 1000))

    # ── Sync path (Appium native) ─────────────────────────────────────────────

    def execute_sync(self, action: AgentAction, step: int) -> StepTrace:
        trace = StepTrace(step=step, action=action.tool_name, action_input=action.tool_input)
        try:
            self._dispatch_sync(action)
            if action.tool_name not in ("done",):
                trace.screenshot_b64 = self.browser.screenshot_base64()
                trace.url = self.browser.current_url()
        except Exception as e:
            trace = self._record_error(trace, action, e)
            try:
                trace.screenshot_b64 = self.browser.screenshot_base64()
            except Exception:
                pass
        return self._apply_assertion(trace, action)

    def _dispatch_sync(self, action: AgentAction):
        n, inp = action.tool_name, action.tool_input
        if n == "navigate":
            self.browser.navigate(inp["url"])
        elif n in ("click", "tap"):
            self.browser.tap(inp["selector"])
        elif n == "type_text":
            self.browser.type_text(inp["selector"], inp["text"])
        elif n == "scroll":
            self.browser.scroll(inp.get("direction", "down"), inp.get("amount", 300))
        elif n == "swipe":
            self.browser.swipe(inp.get("direction", "up"), inp.get("element"))
        elif n == "wait":
            self.browser.wait(inp.get("ms", 1000))

    # ── Shared helpers ────────────────────────────────────────────────────────

    def _apply_assertion(self, trace: StepTrace, action: AgentAction) -> StepTrace:
        if action.tool_name == "assert_condition":
            passed = action.tool_input.get("passed", True)
            trace.assertion_passed = passed
            if not passed:
                trace.finding = {
                    "severity": action.tool_input.get("severity", "medium"),
                    "title": action.tool_input.get("condition", "Assertion failed"),
                    "description": action.tool_input.get("condition", ""),
                    "expected": action.tool_input.get("expected", ""),
                    "actual": action.tool_input.get("actual", ""),
                    "step_index": trace.step,
                    "screenshot_url": "",
                }
        return trace

    def _record_error(self, trace: StepTrace, action: AgentAction, exc: Exception) -> StepTrace:
        trace.finding = {
            "severity": "high",
            "title": f"Action failed: {action.tool_name}",
            "description": str(exc),
            "expected": "Action succeeds",
            "actual": str(exc),
            "step_index": trace.step,
            "screenshot_url": "",
        }
        return trace
