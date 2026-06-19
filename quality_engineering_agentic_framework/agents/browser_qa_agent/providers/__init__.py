from .base import LLMProvider, AgentAction, AGENT_TOOLS_SCHEMA
from .anthropic_provider import AnthropicProvider
from .openai_provider import OpenAIProvider
from .gemini_provider import GeminiProvider
from .ollama_provider import OllamaProvider


def get_provider(name: str, **kwargs) -> LLMProvider:
    """
    Factory to get an LLM provider by name.

    Usage:
        get_provider("anthropic", api_key="sk-ant-...", model="claude-sonnet-4-6")
        get_provider("openai", api_key="sk-...", model="gpt-4o")
        get_provider("azure_openai", api_key="...", model="gpt-4o", base_url="https://...")
        get_provider("gemini", api_key="...", model="gemini-1.5-pro-latest")
        get_provider("ollama", model="llava", base_url="http://localhost:11434")
    """
    name = name.lower()
    if name == "anthropic":
        return AnthropicProvider(**kwargs)
    elif name in ("openai", "azure_openai"):
        return OpenAIProvider(**kwargs)
    elif name == "gemini":
        return GeminiProvider(**kwargs)
    elif name == "ollama":
        return OllamaProvider(**kwargs)
    else:
        raise ValueError(
            f"Unknown provider '{name}'. Supported: anthropic, openai, azure_openai, gemini, ollama"
        )


__all__ = [
    "LLMProvider", "AgentAction", "AGENT_TOOLS_SCHEMA",
    "AnthropicProvider", "OpenAIProvider", "GeminiProvider", "OllamaProvider",
    "get_provider",
]
