"""
GitHub Copilot LLM Implementation

Uses the GitHub Models API (OpenAI-compatible endpoint) with a GitHub token.
No separate OpenAI key needed — the same token that powers Copilot in VS Code.

Endpoint: https://models.inference.ai.azure.com
Auth:     GitHub Personal Access Token (GITHUB_TOKEN)
Models:   gpt-4o, gpt-4o-mini, etc.
"""

import json
import re
from typing import Dict, Optional, Any

from openai import AsyncOpenAI

from quality_engineering_agentic_framework.llm.llm_interface import LLMInterface
from quality_engineering_agentic_framework.utils.logger import get_logger

logger = get_logger(__name__)

GITHUB_MODELS_BASE_URL = "https://models.inference.ai.azure.com"


def _recover_truncated_json(content: str) -> str:
    """Attempt to recover a truncated JSON string by closing open structures."""
    try:
        json.loads(content)
        return content
    except json.JSONDecodeError:
        pass

    for i in range(len(content) - 1, -1, -1):
        if content[i] == '}':
            candidate = content[:i + 1]
            depth_brace   = candidate.count('{') - candidate.count('}')
            depth_bracket = candidate.count('[') - candidate.count(']')
            closers = (']' * depth_bracket) + ('}' * depth_brace)
            try:
                json.loads(candidate + closers)
                logger.warning(
                    f"JSON recovery: trimmed {len(content) - i - 1} chars, added: {repr(closers)}"
                )
                return candidate + closers
            except json.JSONDecodeError:
                continue

    return content


def _extract_json_from_text(content: str) -> str:
    """
    Pull the first JSON object or array out of a free-text response.
    Used as a fallback when response_format=json_object is not supported.
    """
    # Try the whole string first
    try:
        json.loads(content)
        return content
    except json.JSONDecodeError:
        pass

    # Strip markdown code fences
    fenced = re.search(r'```(?:json)?\s*([\s\S]+?)\s*```', content)
    if fenced:
        candidate = fenced.group(1).strip()
        try:
            json.loads(candidate)
            return candidate
        except json.JSONDecodeError:
            content = candidate

    # Find the outermost { ... } or [ ... ]
    for start_char, end_char in [('{', '}'), ('[', ']')]:
        start = content.find(start_char)
        if start == -1:
            continue
        end = content.rfind(end_char)
        if end == -1:
            continue
        candidate = content[start:end + 1]
        try:
            json.loads(candidate)
            return candidate
        except json.JSONDecodeError:
            candidate = _recover_truncated_json(candidate)
            try:
                json.loads(candidate)
                return candidate
            except json.JSONDecodeError:
                continue

    return content


class CopilotLLM(LLMInterface):
    """
    LLM implementation that calls GitHub Models API using a GitHub token.
    API is OpenAI-compatible, so we reuse the openai SDK.
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.model       = config.get("model", "gpt-4o")
        self.temperature = config.get("temperature", 0.2)
        self.max_tokens  = config.get("max_tokens", 8000)

        github_token = config.get("api_key", "")
        if not github_token:
            raise ValueError(
                "GitHub token is required for CopilotLLM. "
                "Set GITHUB_TOKEN environment variable."
            )

        base_url = config.get("base_url", GITHUB_MODELS_BASE_URL)

        self.client = AsyncOpenAI(
            api_key=github_token,
            base_url=base_url,
        )

        logger.info(
            f"Initialized CopilotLLM — model: {self.model}, endpoint: {base_url}"
        )

    async def generate(
        self,
        prompt: str,
        system_message: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        messages = []
        if system_message:
            messages.append({"role": "system", "content": system_message})
        messages.append({"role": "user", "content": prompt})

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature if temperature is not None else self.temperature,
                max_tokens=max_tokens if max_tokens is not None else self.max_tokens,
            )
            return response.choices[0].message.content

        except Exception as e:
            logger.error(f"CopilotLLM generate error: {e}")
            raise

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

        json_max_tokens = max(self.max_tokens, 8000)

        # First attempt: use response_format (supported for gpt-4o on GitHub Models)
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_message},
                    {"role": "user",   "content": prompt},
                ],
                temperature=self.temperature,
                max_tokens=json_max_tokens,
                response_format={"type": "json_object"},
            )
            content = response.choices[0].message.content
            if response.choices[0].finish_reason == "length":
                logger.warning("Response truncated (finish_reason=length). Attempting recovery.")
                content = _recover_truncated_json(content)
            return json.loads(content)

        except Exception as e:
            # Fallback: some Copilot models don't support response_format
            # — ask for JSON via prompt only and extract it from free text
            if "response_format" in str(e).lower() or "json_object" in str(e).lower() or "unsupported" in str(e).lower():
                logger.warning(
                    f"response_format not supported by model '{self.model}'. "
                    "Falling back to prompt-based JSON extraction."
                )
                try:
                    response = await self.client.chat.completions.create(
                        model=self.model,
                        messages=[
                            {"role": "system", "content": system_message},
                            {"role": "user",   "content": prompt},
                        ],
                        temperature=self.temperature,
                        max_tokens=json_max_tokens,
                    )
                    content = response.choices[0].message.content
                    content = _extract_json_from_text(content)
                    return json.loads(content)
                except Exception as fallback_error:
                    logger.error(f"Fallback JSON extraction failed: {fallback_error}")
                    raise

            logger.error(f"CopilotLLM generate_with_json_output error: {e}")
            raise

    def get_provider_name(self) -> str:
        return "copilot"
