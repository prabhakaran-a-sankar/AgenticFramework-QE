"""Base module interface for accessibility testing modules."""

from abc import ABC, abstractmethod
from typing import List
from quality_engineering_agentic_framework.iaa.core.models import AccessibilityIssue


class AccessibilityModule(ABC):
    """Abstract base class for all accessibility testing modules."""
    
    def __init__(self, config: dict | None = None) -> None:
        """Initialize the module with optional configuration."""
        self.config = config or {}
    
    @abstractmethod
    async def run(self, target: str) -> List[AccessibilityIssue]:
        """
        Execute accessibility tests on the target.
        
        Args:
            target: URL, file path, or app identifier to test
            
        Returns:
            List of accessibility issues found
        """
        pass
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Return the module name."""
        pass
    
    def cleanup(self) -> None:
        """Cleanup resources after testing."""
        pass

