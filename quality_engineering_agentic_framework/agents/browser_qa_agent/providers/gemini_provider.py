import json
import base64
import google.generativeai as genai
from google.generativeai.types import FunctionDeclaration, Tool
from .base import LLMProvider, AgentAction, AGENT_TOOLS_SCHEMA, SYSTEM_PROMPT


def _to_gemini_tool(schema: list[dict]) -> Tool:
    declarations = []
    for t in schema:
        params = t["parameters"].copy()
        # Gemini uses "properties" directly
        declarations.append(
            FunctionDeclaration(
                name=t["name"],
                description=t["description"],
                parameters=params,
            )
        )
    return Tool(function_declarations=declarations)


class GeminiProvider(LLMProvider):
    """Google Gemini Pro Vision provider."""

    def __init__(self, api_key: str, model: str = "gemini-1.5-pro-latest"):
        genai.configure(api_key=api_key)
        self.model_name = model
        self._tool = _to_gemini_tool(AGENT_TOOLS_SCHEMA)

    def next_action(self, test_goal, screenshot_b64, dom_snapshot, history, current_url, platform="web") -> AgentAction:
        model = genai.GenerativeModel(
            model_name=self.model_name,
            system_instruction=SYSTEM_PROMPT,
            tools=[self._tool],
        )

        img_bytes = base64.standard_b64decode(screenshot_b64)
        prompt = (
            f"Test goal: {test_goal}\nPlatform: {platform}\n"
            f"Current URL/screen: {current_url}\n"
            f"DOM snapshot:\n{dom_snapshot[:3000]}"
        )

        response = model.generate_content(
            [prompt, {"mime_type": "image/png", "data": img_bytes}],
            tool_config={"function_calling_config": {"mode": "ANY"}},
        )

        for part in response.candidates[0].content.parts:
            if part.function_call:
                fc = part.function_call
                return AgentAction(
                    tool_name=fc.name,
                    tool_input=dict(fc.args),
                )
        return AgentAction(tool_name="done", tool_input={"status": "error", "summary": "No tool call returned"})
