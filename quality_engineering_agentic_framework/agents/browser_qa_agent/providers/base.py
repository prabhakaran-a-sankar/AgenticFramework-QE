from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class AgentAction:
    tool_name: str
    tool_input: dict[str, Any]


# The set of actions every provider must support
AGENT_TOOLS_SCHEMA = [
    {
        "name": "navigate",
        "description": "Navigate the browser to a URL",
        "parameters": {
            "type": "object",
            "properties": {"url": {"type": "string"}},
            "required": ["url"],
        },
    },
    {
        "name": "click",
        "description": "Click an element on the page",
        "parameters": {
            "type": "object",
            "properties": {
                "selector": {"type": "string", "description": "CSS selector or text"},
                "description": {"type": "string"},
            },
            "required": ["selector", "description"],
        },
    },
    {
        "name": "type_text",
        "description": "Type text into an input field",
        "parameters": {
            "type": "object",
            "properties": {"selector": {"type": "string"}, "text": {"type": "string"}},
            "required": ["selector", "text"],
        },
    },
    {
        "name": "tap",
        "description": "Tap an element (mobile gesture)",
        "parameters": {
            "type": "object",
            "properties": {
                "selector": {"type": "string"},
                "description": {"type": "string"},
            },
            "required": ["selector", "description"],
        },
    },
    {
        "name": "swipe",
        "description": "Swipe gesture on mobile (direction: up/down/left/right)",
        "parameters": {
            "type": "object",
            "properties": {
                "direction": {"type": "string", "enum": ["up", "down", "left", "right"]},
                "element": {"type": "string", "description": "Optional element to swipe on"},
            },
            "required": ["direction"],
        },
    },
    {
        "name": "assert_condition",
        "description": "Assert a condition about the current state. Call this to validate expected behaviour.",
        "parameters": {
            "type": "object",
            "properties": {
                "condition": {"type": "string"},
                "passed": {"type": "boolean"},
                "expected": {"type": "string"},
                "actual": {"type": "string"},
                "severity": {"type": "string", "enum": ["critical", "high", "medium", "low", "info"]},
            },
            "required": ["condition", "passed", "expected", "actual", "severity"],
        },
    },
    {
        "name": "scroll",
        "description": "Scroll the page or a mobile screen",
        "parameters": {
            "type": "object",
            "properties": {
                "direction": {"type": "string", "enum": ["up", "down", "left", "right"]},
                "amount": {"type": "integer", "default": 300},
            },
            "required": ["direction"],
        },
    },
    {
        "name": "wait",
        "description": "Wait for a duration in milliseconds",
        "parameters": {
            "type": "object",
            "properties": {"ms": {"type": "integer"}},
            "required": ["ms"],
        },
    },
    {
        "name": "done",
        "description": "Signal the test is complete",
        "parameters": {
            "type": "object",
            "properties": {
                "status": {"type": "string", "enum": ["passed", "failed"]},
                "summary": {"type": "string"},
            },
            "required": ["status", "summary"],
        },
    },
]

SYSTEM_PROMPT = """You are an expert QA testing agent for web and mobile applications. \
Your job is to test applications by interacting with them exactly as a real user would.

You receive:
- A test goal in natural language
- A screenshot of the current state (web browser or mobile device)
- A DOM/accessibility snapshot
- History of actions already taken
- The platform (web | mobile_web | mobile_native)

Choose ONE tool call per turn. Use tap/swipe for mobile_native, click/scroll for web. \
When you find a bug, call assert_condition with passed=false and continue testing. \
Call done() only when the test goal has been fully evaluated.

Rules:
- Use robust selectors (text content, aria labels, data-testid over fragile nth-child)
- For mobile_native: prefer accessibility IDs and resource IDs
- Record ALL bugs, not just the first one
- If an element is not found, try an alternative before giving up
"""


class LLMProvider(ABC):
    """Abstract base for all LLM providers."""

    @abstractmethod
    def next_action(
        self,
        test_goal: str,
        screenshot_b64: str,
        dom_snapshot: str,
        history: list[dict],
        current_url: str,
        platform: str = "web",
    ) -> AgentAction:
        """Given the current browser/device state, return the next action."""
