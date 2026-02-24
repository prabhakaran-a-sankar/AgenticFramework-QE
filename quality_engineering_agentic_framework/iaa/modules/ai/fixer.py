"""AI-powered code fix generator for accessibility issues."""

from typing import Optional, Any


class AIFixer:
    """Generates corrected code for accessibility issues."""
    
    def __init__(self, llm: Optional[Any] = None, offline: bool = False) -> None:
        self.llm = llm
        self.offline = offline
    
    async def generate_fix(
        self,
        rule_id: str,
        broken_code: str,
        wcag_reference: Optional[str] = None
    ) -> dict:
        """
        Generate corrected code for an accessibility issue.
        
        Args:
            rule_id: The accessibility rule identifier
            broken_code: The problematic code snippet
            wcag_reference: WCAG guideline reference
            
        Returns:
            Dictionary with corrected code and explanation
        """
        if self.offline or not self.llm:
            return self._template_fix(rule_id, broken_code)
        return await self._ai_fix(rule_id, broken_code, wcag_reference)
    
    def _template_fix(self, rule_id: str, broken_code: str) -> dict:
        """Generate template-based fix without AI."""
        fixes = {
            "image-alt": {
                "corrected_code": broken_code.replace("<img ", '<img alt="Descriptive text here" '),
                "explanation": "Added alt attribute with placeholder text. Replace with actual description of the image content.",
                "minimal_change": True
            },
            "label": {
                "corrected_code": f'<label for="input-id">Label text</label>\n{broken_code.replace("<input ", "<input id=\"input-id\" ")}',
                "explanation": "Added a label element associated with the input. Update the label text and ensure the id is unique.",
                "minimal_change": True
            },
            "document-title": {
                "corrected_code": "<title>Page Title - Site Name</title>",
                "explanation": "Added a descriptive title element. Update with actual page and site name.",
                "minimal_change": True
            }
        }
        
        default = {
            "corrected_code": broken_code,
            "explanation": f"Manual review required for {rule_id}. Consult WCAG guidelines for specific remediation steps.",
            "minimal_change": False
        }
        
        return fixes.get(rule_id, default)
    
    async def _ai_fix(
        self,
        rule_id: str,
        broken_code: str,
        wcag_reference: Optional[str]
    ) -> dict:
        """Generate AI-powered fix using QEAF LLM."""
        prompt = f"""You are an accessibility expert. Fix this HTML code to resolve the WCAG violation.

Rule: {rule_id}
Broken code: {broken_code}
WCAG: {wcag_reference or 'N/A'}

Provide ONLY the corrected HTML code with minimal changes. Be concise."""
        try:
            corrected = await self.llm.generate(prompt)
            return {
                "corrected_code": corrected.strip(),
                "explanation": "AI-generated fix",
                "minimal_change": True
            }
        except Exception as e:
            print(f"LLM error: {e}. Falling back to template mode.")
        return self._template_fix(rule_id, broken_code)

