"""JSON reporter for accessibility test results."""

import json
from pathlib import Path
from typing import Optional
from quality_engineering_agentic_framework.iaa.core.models import TestResult


class JSONReporter:
    """Generates JSON reports from test results."""
    
    def generate(self, result: TestResult, output_path: Optional[Path] = None) -> str:
        """
        Generate JSON report.
        
        Args:
            result: Test result to report
            output_path: Optional file path to write report
            
        Returns:
            JSON string of the report
        """
        report = {
            "target": result.target,
            "timestamp": result.timestamp.isoformat(),
            "duration_seconds": result.duration_seconds,
            "summary": {
                "total_issues": result.total_issues,
                "critical": result.critical_count,
                "serious": result.serious_count,
                "moderate": result.moderate_count,
                "minor": result.minor_count
            },
            "issues": [
                {
                    "rule_id": issue.rule_id,
                    "category": issue.category.value,
                    "severity": issue.severity.value,
                    "description": issue.description,
                    "wcag_reference": issue.wcag_reference,
                    "element": issue.element,
                    "selector": issue.selector,
                    "recommendation": issue.recommendation,
                    "ai_explanation": issue.ai_explanation,
                    "ai_fix": issue.ai_fix,
                    "impact": issue.impact
                }
                for issue in result.issues
            ]
        }
        
        json_str = json.dumps(report, indent=2)
        
        if output_path:
            output_path.write_text(json_str, encoding="utf-8")
        
        return json_str

