"""
Base interface for all agents in the framework.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any

from quality_engineering_agentic_framework.llm.llm_interface import LLMInterface


class AgentInterface(ABC):
    """Base interface for all agents."""

    def __init__(self, llm: LLMInterface, config: Dict[str, Any]):
        self.llm = llm
        self.config = config

    @abstractmethod
    async def process(self, input_data: Any) -> Any:
        pass
