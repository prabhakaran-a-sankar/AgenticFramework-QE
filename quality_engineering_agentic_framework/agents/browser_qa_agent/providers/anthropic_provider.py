import anthropic
from .base import LLMProvider, AgentAction, AGENT_TOOLS_SCHEMA, SYSTEM_PROMPT


def _to_anthropic_tool(t: dict) -> dict:
    return {
        "name": t["name"],
        "description": t["description"],
        "input_schema": t["parameters"],
    }


class AnthropicProvider(LLMProvider):
    def __init__(self, api_key: str, model: str = "claude-sonnet-4-6"):
        self._client = anthropic.Anthropic(api_key=api_key)
        self.model = model

    def next_action(self, test_goal, screenshot_b64, dom_snapshot, history, current_url, platform="web") -> AgentAction:
        messages = self._build_messages(test_goal, screenshot_b64, dom_snapshot, history, current_url, platform)
        tools = [_to_anthropic_tool(t) for t in AGENT_TOOLS_SCHEMA]

        response = self._client.messages.create(
            model=self.model,
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            tools=tools,
            tool_choice={"type": "any"},
            messages=messages,
        )
        for block in response.content:
            if block.type == "tool_use":
                return AgentAction(tool_name=block.name, tool_input=block.input)
        return AgentAction(tool_name="done", tool_input={"status": "error", "summary": "No tool call returned"})

    def _build_messages(self, test_goal, screenshot_b64, dom_snapshot, history, current_url, platform):
        messages = []
        for entry in history:
            messages.append({"role": "user", "content": entry["user"]})
            messages.append({"role": "assistant", "content": entry["assistant"]})

        messages.append({
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": (
                        f"Test goal: {test_goal}\n"
                        f"Platform: {platform}\n"
                        f"Current URL/screen: {current_url}\n"
                        f"DOM/Accessibility snapshot:\n{dom_snapshot[:3000]}\n\nScreenshot:"
                    ),
                },
                {
                    "type": "image",
                    "source": {"type": "base64", "media_type": "image/png", "data": screenshot_b64},
                },
            ],
        })
        return messages
