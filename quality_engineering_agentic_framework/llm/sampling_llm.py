"""
MCP Sampling LLM Implementation

Delegates all generation to the MCP *host* (e.g. GitHub Copilot in VS Code)
via the MCP `sampling/createMessage` request. The host runs the completion
using whatever model the user has selected, so this provider needs
NO API key and NO token of its own.

This is an MCP-only provider — it requires a live MCP request Context and
is never wired into the UI or the shared LLMFactory.

Requires a client that supports MCP sampling (recent VS Code Copilot does;
some clients do not). The caller is responsible for falling back to a
key/token-based provider when sampling is unavailable.
"""

import json
from typing import Dict, Optional, Any

from mcp.types import SamplingMessage, TextContent

from quality_engineering_agentic_framework.llm.llm_interface import LLMInterface
from quality_engineering_agentic_framework.llm.copilot_llm import (
    _recover_truncated_json,
    _extract_json_from_text,
)
from quality_engineering_agentic_framework.utils.logger import get_logger

logger = get_logger(__name__)


class SamplingNotSupportedError(RuntimeError):
    """Raised when the connected MCP host does not support sampling."""


# Many host models (via the VS Code sampling bridge) cap output well below 8k;
# requesting more can make them return "no choices". Keep requests conservative.
_SAMPLING_MAX_TOKENS_CAP = 4096
_SAMPLING_RETRY_TOKENS = 2048


def _is_sampling_unsupported(error: Exception) -> bool:
    """Detect the 'Method not found: sampling/createMessage' class of errors."""
    msg = str(error).lower()
    return (
        "method not found" in msg
        or "sampling/createmessage" in msg
        or "no client capabilities" in msg
        or "does not support sampling" in msg
    )


def _is_empty_response(error: Exception) -> bool:
    """Host accepted the request but the model returned nothing usable."""
    msg = str(error).lower()
    return "no choices" in msg or "empty response" in msg or "no completion" in msg


class SamplingLLM(LLMInterface):
    """
    LLM implementation that asks the MCP host to run completions on our behalf.

    Pass the FastMCP `Context` from inside an @mcp.tool() function. We use
    ctx.session.create_message(...) to request a completion from the host model.
    """

    def __init__(self, ctx: Any, config: Optional[Dict[str, Any]] = None):
        config = config or {}
        self.ctx = ctx
        self.temperature = config.get("temperature", 0.2)
        self.max_tokens = config.get("max_tokens", _SAMPLING_MAX_TOKENS_CAP)
        logger.info("Initialized SamplingLLM — generation delegated to MCP host")

    @staticmethod
    def _extract_text(result) -> str:
        content = result.content
        # content is a single content block (TextContent), or a list of them.
        if isinstance(content, list):
            return "\n".join(
                c.text for c in content if getattr(c, "type", None) == "text"
            )
        if getattr(content, "type", None) == "text":
            return content.text or ""
        return str(content) if content is not None else ""

    async def _create_message(
        self,
        prompt: str,
        system_message: Optional[str],
        temperature: Optional[float],
        max_tokens: Optional[int],
    ) -> str:
        messages = [
            SamplingMessage(
                role="user",
                content=TextContent(type="text", text=prompt),
            )
        ]
        temp = temperature if temperature is not None else self.temperature
        requested = max_tokens if max_tokens is not None else self.max_tokens

        # Clamp to a host-friendly size; if the model still returns nothing,
        # retry once with a smaller budget (a frequent cause of "no choices").
        first = min(requested, _SAMPLING_MAX_TOKENS_CAP)
        budgets = [first] + ([_SAMPLING_RETRY_TOKENS] if first > _SAMPLING_RETRY_TOKENS else [])

        last_exc: Optional[Exception] = None
        for i, mt in enumerate(budgets):
            try:
                result = await self.ctx.session.create_message(
                    messages=messages,
                    max_tokens=mt,
                    system_prompt=system_message,
                    temperature=temp,
                )
            except Exception as e:
                if _is_sampling_unsupported(e):
                    logger.warning(f"MCP host does not support sampling: {e}")
                    raise SamplingNotSupportedError(str(e)) from e
                if _is_empty_response(e) and i + 1 < len(budgets):
                    logger.warning(
                        f"Host returned no choices (max_tokens={mt}); "
                        f"retrying with {budgets[i + 1]}."
                    )
                    last_exc = e
                    continue
                logger.error(f"SamplingLLM create_message error: {e}")
                raise

            text = self._extract_text(result)
            if text.strip():
                return text
            if i + 1 < len(budgets):
                logger.warning(
                    f"Host returned empty content (max_tokens={mt}); "
                    f"retrying with {budgets[i + 1]}."
                )
                continue
            return text  # final attempt — hand back whatever we got

        raise RuntimeError(
            "Host model returned no content (sampling produced no choices). "
            "Try a different Copilot model, or reduce the request size. "
            f"Last error: {last_exc}"
        )

    async def generate(
        self,
        prompt: str,
        system_message: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        return await self._create_message(prompt, system_message, temperature, max_tokens)

    async def generate_with_json_output(
        self,
        prompt: str,
        json_schema: Dict[str, Any],
        system_message: Optional[str] = None,
    ) -> Dict[str, Any]:
        if not system_message:
            system_message = "You are a helpful assistant that responds in JSON format."

        system_message += (
            f"\nYou must respond with a valid JSON object that conforms to this schema: "
            f"{json.dumps(json_schema)}"
            f"\nReturn only the JSON object — no explanation, no markdown fences."
        )

        content = await self._create_message(
            prompt, system_message, self.temperature, self.max_tokens
        )

        # Hosts return free text; extract and repair JSON from it.
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            extracted = _extract_json_from_text(content)
            try:
                return json.loads(extracted)
            except json.JSONDecodeError:
                repaired = _recover_truncated_json(extracted)
                return json.loads(repaired)

    def get_provider_name(self) -> str:
        return "sampling"
