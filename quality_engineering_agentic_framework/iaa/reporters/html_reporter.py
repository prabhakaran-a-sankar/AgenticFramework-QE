"""HTML reporter for accessibility test results."""

from pathlib import Path
from typing import Optional
from jinja2 import Template
from quality_engineering_agentic_framework.iaa.core.models import TestResult


HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Accessibility Report - {{ result.target }}</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; line-height: 1.6; color: #333; background: #f5f5f5; padding: 20px; }
        .container { max-width: 1200px; margin: 0 auto; background: white; padding: 30px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        h1 { color: #2c3e50; margin-bottom: 10px; }
        .meta { color: #7f8c8d; margin-bottom: 30px; }
        .summary { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 15px; margin-bottom: 30px; }
        .summary-card { padding: 20px; border-radius: 6px; text-align: center; }
        .summary-card h3 { font-size: 32px; margin-bottom: 5px; }
        .summary-card p { color: #7f8c8d; font-size: 14px; }
        .critical-card { background: #fee; border-left: 4px solid #e74c3c; }
        .serious-card { background: #fff3e0; border-left: 4px solid #f39c12; }
        .moderate-card { background: #fff9e6; border-left: 4px solid #f1c40f; }
        .minor-card { background: #e8f5e9; border-left: 4px solid #27ae60; }
        .issue { background: #fafafa; border-left: 4px solid #3498db; padding: 20px; margin-bottom: 20px; border-radius: 4px; }
        .issue.critical { border-left-color: #e74c3c; }
        .issue.serious { border-left-color: #f39c12; }
        .issue.moderate { border-left-color: #f1c40f; }
        .issue.minor { border-left-color: #27ae60; }
        .issue-header { display: flex; justify-content: space-between; align-items: start; margin-bottom: 15px; }
        .issue-title { font-size: 18px; font-weight: 600; color: #2c3e50; }
        .severity-badge { padding: 4px 12px; border-radius: 12px; font-size: 12px; font-weight: 600; text-transform: uppercase; }
        .severity-critical { background: #e74c3c; color: white; }
        .severity-serious { background: #f39c12; color: white; }
        .severity-moderate { background: #f1c40f; color: #333; }
        .severity-minor { background: #27ae60; color: white; }
        .issue-description { margin-bottom: 10px; color: #555; }
        .code-block { background: #2c3e50; color: #ecf0f1; padding: 15px; border-radius: 4px; overflow-x: auto; margin: 10px 0; font-family: 'Courier New', monospace; font-size: 14px; }
        .ai-section { background: #e8f4f8; padding: 15px; border-radius: 4px; margin-top: 10px; }
        .ai-section h4 { color: #2980b9; margin-bottom: 8px; font-size: 14px; }
        .wcag-ref { color: #3498db; text-decoration: none; font-size: 14px; }
        .wcag-ref:hover { text-decoration: underline; }
    </style>
</head>
<body>
    <div class="container">
        <h1>Accessibility Test Report</h1>
        <div class="meta">
            <p><strong>Target:</strong> {{ result.target }}</p>
            <p><strong>Tested:</strong> {{ result.timestamp.strftime('%Y-%m-%d %H:%M:%S') }}</p>
            <p><strong>Duration:</strong> {{ "%.2f"|format(result.duration_seconds) }}s</p>
        </div>
        
        <div class="summary">
            <div class="summary-card critical-card">
                <h3>{{ result.critical_count }}</h3>
                <p>Critical</p>
            </div>
            <div class="summary-card serious-card">
                <h3>{{ result.serious_count }}</h3>
                <p>Serious</p>
            </div>
            <div class="summary-card moderate-card">
                <h3>{{ result.moderate_count }}</h3>
                <p>Moderate</p>
            </div>
            <div class="summary-card minor-card">
                <h3>{{ result.minor_count }}</h3>
                <p>Minor</p>
            </div>
        </div>
        
        <h2 style="margin-bottom: 20px;">Issues Found ({{ result.total_issues }})</h2>
        
        {% for issue in result.issues %}
        <div class="issue {{ issue.severity.value }}">
            <div class="issue-header">
                <div class="issue-title">{{ issue.description }}</div>
                <span class="severity-badge severity-{{ issue.severity.value }}">{{ issue.severity.value }}</span>
            </div>
            
            <p class="issue-description"><strong>Rule:</strong> {{ issue.rule_id }}</p>
            
            {% if issue.wcag_reference %}
            <p><a href="{{ issue.wcag_reference }}" class="wcag-ref" target="_blank">WCAG Reference →</a></p>
            {% endif %}
            
            {% if issue.element %}
            <div class="code-block">{{ issue.element }}</div>
            {% endif %}
            
            {% if issue.ai_explanation %}
            <div class="ai-section">
                <h4>🤖 AI Explanation</h4>
                <p>{{ issue.ai_explanation }}</p>
                {% if issue.impact %}
                <p style="margin-top: 8px;"><strong>Impact:</strong> {{ issue.impact }}</p>
                {% endif %}
            </div>
            {% endif %}
            
            {% if issue.ai_fix %}
            <div class="ai-section" style="background: #e8f5e9;">
                <h4>✨ Suggested Fix</h4>
                <div class="code-block">{{ issue.ai_fix }}</div>
            </div>
            {% endif %}
            
            {% if issue.recommendation %}
            <p style="margin-top: 10px; color: #555;"><strong>Recommendation:</strong> {{ issue.recommendation }}</p>
            {% endif %}
        </div>
        {% endfor %}
    </div>
</body>
</html>
"""


class HTMLReporter:
    """Generates HTML reports from test results."""
    
    def generate(self, result: TestResult, output_path: Optional[Path] = None) -> str:
        """
        Generate HTML report.
        
        Args:
            result: Test result to report
            output_path: Optional file path to write report
            
        Returns:
            HTML string of the report
        """
        template = Template(HTML_TEMPLATE)
        html = template.render(result=result)
        
        if output_path:
            output_path.write_text(html, encoding="utf-8")
        
        return html

