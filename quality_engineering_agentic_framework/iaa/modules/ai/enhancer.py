"""AI enhancement wrapper for accessibility testing."""

from typing import List, Optional, Any
from quality_engineering_agentic_framework.iaa.core.models import AccessibilityIssue
from quality_engineering_agentic_framework.iaa.modules.ai.explainer import AIExplainer
from quality_engineering_agentic_framework.iaa.modules.ai.fixer import AIFixer


class AIEnhancer:
    """Enhances accessibility issues with AI-generated explanations and fixes."""
    
    def __init__(self, llm: Optional[Any] = None, offline: bool = False, enabled: bool = True) -> None:
        self.enabled = enabled
        self.explainer = AIExplainer(llm=llm, offline=offline)
        self.fixer = AIFixer(llm=llm, offline=offline)
    
    async def enhance_issues(
        self,
        issues: List[AccessibilityIssue]
    ) -> List[AccessibilityIssue]:
        """
        Enhance issues with AI explanations and fixes.
        
        Args:
            issues: List of accessibility issues to enhance
            
        Returns:
            Enhanced list of issues with AI data populated
        """
        if not self.enabled:
            return issues
        
        for issue in issues:
            # Generate explanation
            explanation = await self.explainer.explain(
                rule_id=issue.rule_id,
                description=issue.description,
                element=issue.element,
                wcag_reference=issue.wcag_reference
            )
            
            issue.ai_explanation = explanation.get("explanation")
            issue.impact = explanation.get("impact")
            
            # Generate fix if element code is available
            if issue.element:
                fix = await self.fixer.generate_fix(
                    rule_id=issue.rule_id,
                    broken_code=issue.element,
                    wcag_reference=issue.wcag_reference
                )
                issue.ai_fix = fix.get("corrected_code")
        
        return issues

