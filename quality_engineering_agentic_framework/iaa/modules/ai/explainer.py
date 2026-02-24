"""AI-powered accessibility issue explainer."""

from typing import Optional, Any


class AIExplainer:
    """Generates plain-language explanations for accessibility issues."""
    
    def __init__(self, llm: Optional[Any] = None, offline: bool = False) -> None:
        self.llm = llm
        self.offline = offline
    
    async def explain(
        self,
        rule_id: str,
        description: str,
        element: Optional[str] = None,
        wcag_reference: Optional[str] = None
    ) -> dict:
        """
        Generate explanation for an accessibility issue.
        
        Args:
            rule_id: The accessibility rule identifier
            description: Brief description of the issue
            element: HTML/code snippet of the problematic element
            wcag_reference: WCAG guideline reference
            
        Returns:
            Dictionary with explanation, impact, and recommended fix
        """
        if self.offline or not self.llm:
            return self._offline_explain(rule_id, description, element, wcag_reference)
        return await self._ai_explain(rule_id, description, element, wcag_reference)
    
    def _offline_explain(
        self,
        rule_id: str,
        description: str,
        element: Optional[str],
        wcag_reference: Optional[str]
    ) -> dict:
        """Generate rule-based explanation without AI."""
        explanations = {
            "image-alt": {
                "explanation": "Images without alternative text are invisible to screen readers. Users who are blind or have low vision cannot understand the content or purpose of the image.",
                "impact": "Critical - Screen reader users will miss important visual information",
                "recommended_fix": "Add an alt attribute with descriptive text to the <img> tag"
            },
            "label": {
                "explanation": "Form inputs without labels make it impossible for screen reader users to understand what information to enter. The label provides context and purpose.",
                "impact": "Critical - Users cannot complete forms independently",
                "recommended_fix": "Add a <label> element associated with the input using the 'for' attribute"
            },
            "document-title": {
                "explanation": "The page title appears in browser tabs and is the first thing announced by screen readers. Without it, users cannot identify the page content or navigate between tabs.",
                "impact": "Serious - Users cannot identify page content or navigate effectively",
                "recommended_fix": "Add a descriptive <title> element in the <head> section"
            }
        }
        
        default = {
            "explanation": f"{description}. This violates accessibility standards and may prevent users with disabilities from accessing content.",
            "impact": "This issue affects users who rely on assistive technologies",
            "recommended_fix": f"Review {wcag_reference or 'WCAG guidelines'} for remediation steps"
        }
        
        result = explanations.get(rule_id, default)
        result["wcag_reference"] = wcag_reference or "WCAG 2.2"
        
        return result
    
    async def _ai_explain(
        self,
        rule_id: str,
        description: str,
        element: Optional[str],
        wcag_reference: Optional[str]
    ) -> dict:
        """Generate AI-powered explanation using QEAF LLM."""
        prompt = f"""You are an accessibility expert. Explain this WCAG violation in simple terms.

Rule: {rule_id}
Description: {description}
Code: {element or 'N/A'}
WCAG: {wcag_reference or 'N/A'}

Provide a clear explanation (2-3 sentences), impact on users with disabilities, and a brief recommendation. Be concise."""
        try:
            ai_text = await self.llm.generate(prompt)
            return {
                "explanation": ai_text,
                "impact": "AI-generated impact analysis",
                "wcag_reference": wcag_reference or "WCAG 2.2"
            }
        except Exception as e:
            print(f"LLM error: {e}. Falling back to offline mode.")
        return self._offline_explain(rule_id, description, element, wcag_reference)

