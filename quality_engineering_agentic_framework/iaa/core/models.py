"""Core data models for the Intelligent Accessibility Assistant."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List, Dict, Any
from datetime import datetime


class Severity(str, Enum):
    """Severity levels for accessibility issues."""
    CRITICAL = "critical"
    SERIOUS = "serious"
    MODERATE = "moderate"
    MINOR = "minor"
    INFO = "info"


class Category(str, Enum):
    """Categories of accessibility issues."""
    WCAG_A = "wcag_a"
    WCAG_AA = "wcag_aa"
    WCAG_AAA = "wcag_aaa"
    ARIA = "aria"
    KEYBOARD = "keyboard"
    COLOR_CONTRAST = "color_contrast"
    MOBILE = "mobile"
    BEST_PRACTICE = "best_practice"


@dataclass
class AccessibilityIssue:
    """Represents a single accessibility issue."""
    
    rule_id: str
    category: Category
    severity: Severity
    description: str
    wcag_reference: Optional[str] = None
    element: Optional[str] = None
    selector: Optional[str] = None
    recommendation: Optional[str] = None
    ai_explanation: Optional[str] = None
    ai_fix: Optional[str] = None
    impact: Optional[str] = None
    screenshot_path: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TestResult:
    """Represents the complete test result."""
    
    target: str
    timestamp: datetime
    issues: List[AccessibilityIssue]
    total_issues: int = 0
    critical_count: int = 0
    serious_count: int = 0
    moderate_count: int = 0
    minor_count: int = 0
    duration_seconds: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self) -> None:
        """Calculate counts after initialization."""
        self.total_issues = len(self.issues)
        self.critical_count = sum(1 for i in self.issues if i.severity == Severity.CRITICAL)
        self.serious_count = sum(1 for i in self.issues if i.severity == Severity.SERIOUS)
        self.moderate_count = sum(1 for i in self.issues if i.severity == Severity.MODERATE)
        self.minor_count = sum(1 for i in self.issues if i.severity == Severity.MINOR)

