"""
Ollama provider — runs local models (llava, llama3.2-vision, etc.).
Requires Ollama running at OLLAMA_BASE_URL (default: http://localhost:11434).
Tool calls are simulated via JSON-mode prompt since Ollama models vary in native tool support.
"""
import json
import httpx
from .base import LLMProvider, AgentAction, AGENT_TOOLS_SCHEMA, SYSTEM_PROMPT

_TOOL_LIST = "\n".join(
    f"- {t['name']}: {t['description']} | params: {json.dumps(t['parameters'].get('properties', {}))}"
    for t in AGENT_TOOLS_SCHEMA
)

_JSON_INSTRUCTION = f"""
You must respond ONLY with a valid JSON object in this exact format:
{{"tool": "<tool_name>", "input": {{...parameters...}}}}

Available tools:
{_TOOL_LIST}
"""


class OllamaProvider(LLMProvider):
    """Local Ollama provider (vision-capable models recommended: llava, llama3.2-vision)."""

    def __init__(self, model: str = "llava", base_url: str = "http://localhost:11434"):
        self.model = model
        self.base_url = base_url.rstrip("/")

    def next_action(self, test_goal, screenshot_b64, dom_snapshot, history, current_url, platform="web") -> AgentAction:
        prompt = (
            f"{SYSTEM_PROMPT}\n{_JSON_INSTRUCTION}\n\n"
            f"Test goal: {test_goal}\nPlatform: {platform}\n"
            f"Current URL/screen: {current_url}\n"
            f"DOM snapshot:\n{dom_snapshot[:2000]}\n\n"
            "What is the next action? Respond only with JSON."
        )

        payload = {
            "model": self.model,
            "prompt": prompt,
            "images": [screenshot_b64],
            "stream": False,
            "format": "json",
        }

        with httpx.Client(timeout=120) as client:
            resp = client.post(f"{self.base_url}/api/generate", json=payload)
            resp.raise_for_status()
            raw = resp.json().get("response", "{}")

        try:
            parsed = json.loads(raw)
            return AgentAction(
                tool_name=parsed.get("tool", "done"),
                tool_input=parsed.get("input", {"status": "error", "summary": "Malformed response"}),
            )
        except (json.JSONDecodeError, KeyError):
            return AgentAction(tool_name="done", tool_input={"status": "error", "summary": f"Parse error: {raw[:200]}"})
