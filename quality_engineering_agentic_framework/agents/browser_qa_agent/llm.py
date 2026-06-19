"""
Thin compatibility shim — LLMClient now wraps a pluggable provider.
Use providers.get_provider() directly for full control.
"""
from .providers import LLMProvider, AgentAction, get_provider
from .config import get_settings


class LLMClient:
    """
    Default LLM client — reads provider config from environment.
    Override by passing a provider instance to QAPlanner directly.
    """

    def __init__(self, provider: LLMProvider | None = None):
        if provider:
            self._provider = provider
        else:
            settings = get_settings()
            self._provider = self._from_settings(settings)

    @staticmethod
    def _from_settings(settings) -> LLMProvider:
        name = settings.llm_provider.lower()
        if name == "anthropic":
            return get_provider("anthropic", api_key=settings.anthropic_api_key, model=settings.llm_model)
        elif name in ("openai", "azure_openai"):
            return get_provider(
                name,
                api_key=settings.openai_api_key,
                model=settings.llm_model,
                base_url=settings.azure_openai_endpoint or None,
                api_version=settings.azure_openai_api_version or None,
            )
        elif name == "gemini":
            return get_provider("gemini", api_key=settings.gemini_api_key, model=settings.llm_model)
        elif name == "ollama":
            return get_provider("ollama", model=settings.llm_model, base_url=settings.ollama_base_url)
        else:
            raise ValueError(f"Unknown LLM_PROVIDER: {name}")

    def next_action(
        self,
        test_goal: str,
        screenshot_b64: str,
        dom_snapshot: str,
        history: list[dict],
        current_url: str,
        platform: str = "web",
    ) -> AgentAction:
        return self._provider.next_action(
            test_goal=test_goal,
            screenshot_b64=screenshot_b64,
            dom_snapshot=dom_snapshot,
            history=history,
            current_url=current_url,
            platform=platform,
        )
