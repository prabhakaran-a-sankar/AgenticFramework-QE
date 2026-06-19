import json
from openai import OpenAI
from .base import LLMProvider, AgentAction, AGENT_TOOLS_SCHEMA, SYSTEM_PROMPT


def _to_openai_tool(t: dict) -> dict:
    return {
        "type": "function",
        "function": {
            "name": t["name"],
            "description": t["description"],
            "parameters": t["parameters"],
        },
    }


class OpenAIProvider(LLMProvider):
    """Supports OpenAI GPT-4o/4-turbo and Azure OpenAI."""

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4o",
        base_url: str | None = None,  # set for Azure: https://<resource>.openai.azure.com/
        api_version: str | None = None,  # Azure: e.g. "2024-02-15-preview"
    ):
        kwargs = {"api_key": api_key}
        if base_url:
            kwargs["base_url"] = base_url
        if api_version:
            kwargs["default_headers"] = {"api-version": api_version}
        self._client = OpenAI(**kwargs)
        self.model = model

    def next_action(self, test_goal, screenshot_b64, dom_snapshot, history, current_url, platform="web") -> AgentAction:
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        for entry in history:
            messages.append({"role": "user", "content": entry["user"]})
            messages.append({"role": "assistant", "content": entry["assistant"]})

        messages.append({
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": (
                        f"Test goal: {test_goal}\nPlatform: {platform}\n"
                        f"Current URL/screen: {current_url}\n"
                        f"DOM/Accessibility snapshot:\n{dom_snapshot[:3000]}"
                    ),
                },
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{screenshot_b64}"},
                },
            ],
        })

        tools = [_to_openai_tool(t) for t in AGENT_TOOLS_SCHEMA]
        response = self._client.chat.completions.create(
            model=self.model,
            messages=messages,
            tools=tools,
            tool_choice="required",
            max_tokens=1024,
        )

        msg = response.choices[0].message
        if msg.tool_calls:
            call = msg.tool_calls[0]
            return AgentAction(
                tool_name=call.function.name,
                tool_input=json.loads(call.function.arguments),
            )
        return AgentAction(tool_name="done", tool_input={"status": "error", "summary": "No tool call returned"})
