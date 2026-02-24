"""Core accessibility testing engine."""

import time
from datetime import datetime
from typing import List
from quality_engineering_agentic_framework.iaa.core.module import AccessibilityModule
from quality_engineering_agentic_framework.iaa.core.models import TestResult, AccessibilityIssue


class AccessibilityEngine:
    """Orchestrates accessibility testing across multiple modules."""
    
    def __init__(self, modules: List[AccessibilityModule]) -> None:
        """
        Initialize the engine with testing modules.
        
        Args:
            modules: List of accessibility testing modules to execute
        """
        self.modules = modules
    
    async def execute(self, target: str) -> TestResult:
        """
        Execute all modules against the target.
        
        Args:
            target: URL, file path, or app identifier to test
            
        Returns:
            Complete test result with all issues found
        """
        start_time = time.time()
        all_issues: List[AccessibilityIssue] = []
        
        for module in self.modules:
            try:
                issues = await module.run(target)
                all_issues.extend(issues)
            except Exception as e:
                print(f"Error in module {module.name}: {e}")
                raise
            finally:
                # Prefer async cleanup when available
                if hasattr(module, "cleanup_async"):
                    await module.cleanup_async()
                else:
                    module.cleanup()
        
        duration = time.time() - start_time
        
        return TestResult(
            target=target,
            timestamp=datetime.now(),
            issues=all_issues,
            duration_seconds=duration
        )

