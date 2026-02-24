"""Web accessibility testing module using Playwright and axe-core."""

import os
from pathlib import Path
from typing import List
from playwright.async_api import async_playwright, Page
from quality_engineering_agentic_framework.iaa.core.module import AccessibilityModule
from quality_engineering_agentic_framework.iaa.core.models import AccessibilityIssue, Severity, Category


class WebAccessibilityModule(AccessibilityModule):
    """Tests web applications for accessibility issues."""
    
    def __init__(self, config: dict | None = None) -> None:
        super().__init__(config)
        self.browser = None
        self.context = None
        self.playwright = None
    
    @property
    def name(self) -> str:
        return "web_accessibility"
    
    async def run(self, target: str) -> List[AccessibilityIssue]:
        """Run web accessibility tests using Playwright and axe-core."""
        issues: List[AccessibilityIssue] = []
        
        # Handle file paths
        if os.path.exists(target):
            target = f'file:///{os.path.abspath(target).replace(os.sep, "/")}'
        # Add https:// if no protocol specified
        elif not target.startswith(('http://', 'https://', 'file://')):
            target = f'https://{target}'
        
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(
            headless=self.config.get("headless", True)
        )
        self.context = await self.browser.new_context()
        page = await self.context.new_page()
        
        try:
            await page.goto(target, wait_until="networkidle")
            
            # Inject axe-core
            await self._inject_axe(page)
            
            # Run axe analysis with explicit WCAG 2.x A, AA, and AAA rule sets
            axe_results = await page.evaluate("""
                () => axe.run(document, {
                    runOnly: {
                        type: 'tag',
                        values: ['wcag2a', 'wcag2aa', 'wcag2aaa', 'wcag21a', 'wcag21aa', 'best-practice']
                    }
                })
            """)
            
            # Convert axe results to our format
            issues.extend(self._parse_axe_results(axe_results))
            
            # Additional checks
            issues.extend(await self._check_keyboard_navigation(page))
            
        finally:
            await page.close()
        
        return issues
    
    async def _inject_axe(self, page: Page) -> None:
        """Inject axe-core library into the page."""
        # Load axe-core from resources
        axe_path = Path(__file__).parent.parent / "resources" / "axe-core.js"
        axe_source = axe_path.read_text(encoding="utf-8")
        await page.evaluate(axe_source)
    
    def _parse_axe_results(self, axe_results: dict) -> List[AccessibilityIssue]:
        """Parse axe-core results into AccessibilityIssue objects."""
        issues: List[AccessibilityIssue] = []
        
        for violation in axe_results.get("violations", []):
            severity = self._map_severity(violation.get("impact", "moderate"))
            tags = violation.get("tags", [])
            category = self._map_category(tags)
            wcag_criteria = self._extract_wcag_criteria(tags)
            help_url = violation.get("helpUrl", "")
            wcag_reference = f"{wcag_criteria} ({help_url})".strip(" (")  if wcag_criteria else help_url
            
            for node in violation.get("nodes", []):
                failure_summary = node.get("failureSummary", "")
                issue = AccessibilityIssue(
                    rule_id=violation["id"],
                    category=category,
                    severity=severity,
                    description=violation.get("help", ""),
                    wcag_reference=wcag_reference or help_url,
                    element=node.get("html"),
                    selector=str(node.get("target", [])),
                    recommendation=failure_summary or violation.get("description", "")
                )
                issues.append(issue)
        
        return issues
    
    def _map_category(self, tags: list) -> Category:
        """Map axe-core tags to the most specific WCAG category."""
        if any(t in tags for t in ("wcag2aaa", "wcag21aaa")):
            return Category.WCAG_AAA
        if any(t in tags for t in ("wcag2aa", "wcag21aa")):
            return Category.WCAG_AA
        if any(t in tags for t in ("wcag2a", "wcag21a")):
            return Category.WCAG_A
        if "best-practice" in tags:
            return Category.BEST_PRACTICE
        if "cat.aria" in tags:
            return Category.ARIA
        if "cat.color" in tags:
            return Category.COLOR_CONTRAST
        if "cat.keyboard" in tags:
            return Category.KEYBOARD
        return Category.WCAG_AA
    
    def _extract_wcag_criteria(self, tags: list) -> str:
        """Extract human-readable WCAG success criteria from axe tags (e.g. wcag111 -> 1.1.1)."""
        criteria = []
        for tag in tags:
            # axe encodes criteria as wcag<digits>, e.g. wcag111 -> 1.1.1, wcag143 -> 1.4.3
            if tag.startswith("wcag") and tag[4:].isdigit():
                digits = tag[4:]
                # Format: first digit, then remaining digits each separated by '.'
                formatted = digits[0] + "".join(f".{d}" for d in digits[1:])
                criteria.append(f"WCAG {formatted}")
        return ", ".join(criteria)
    
    def _map_severity(self, impact: str) -> Severity:
        """Map axe impact levels to our severity enum."""
        mapping = {
            "critical": Severity.CRITICAL,
            "serious": Severity.SERIOUS,
            "moderate": Severity.MODERATE,
            "minor": Severity.MINOR,
        }
        return mapping.get(impact.lower(), Severity.MODERATE)
    
    async def _check_keyboard_navigation(self, page: Page) -> List[AccessibilityIssue]:
        """Check for keyboard navigation issues not covered by axe-core."""
        issues: List[AccessibilityIssue] = []
        
        nav_data = await page.evaluate("""
            () => {
                const interactive = Array.from(document.querySelectorAll(
                    'a[href], button, input:not([type="hidden"]), select, textarea, [tabindex]'
                ));
                const positivetabindex = interactive.filter(
                    el => parseInt(el.getAttribute('tabindex'), 10) > 0
                ).length;
                const missingFocusStyle = interactive.filter(el => {
                    const style = window.getComputedStyle(el, ':focus');
                    return style.outlineStyle === 'none' && style.outlineWidth === '0px';
                }).length;
                return {
                    total: interactive.length,
                    positivetabindex: positivetabindex,
                    missingFocusStyle: missingFocusStyle
                };
            }
        """)
        
        if nav_data["total"] == 0:
            issues.append(AccessibilityIssue(
                rule_id="keyboard-no-focusable",
                category=Category.KEYBOARD,
                severity=Severity.SERIOUS,
                description="No keyboard-focusable elements found on page",
                wcag_reference="WCAG 2.1.1",
                recommendation="Ensure interactive elements are keyboard accessible"
            ))
        
        if nav_data["positivetabindex"] > 0:
            issues.append(AccessibilityIssue(
                rule_id="keyboard-tabindex-order",
                category=Category.KEYBOARD,
                severity=Severity.MODERATE,
                description=f"{nav_data['positivetabindex']} element(s) use positive tabindex values, disrupting natural tab order",
                wcag_reference="WCAG 2.4.3",
                recommendation="Remove positive tabindex values and rely on DOM order for focus sequence"
            ))
        
        if nav_data["missingFocusStyle"] > 0:
            issues.append(AccessibilityIssue(
                rule_id="keyboard-focus-visible",
                category=Category.KEYBOARD,
                severity=Severity.SERIOUS,
                description=f"{nav_data['missingFocusStyle']} interactive element(s) have no visible focus indicator",
                wcag_reference="WCAG 2.4.7",
                recommendation="Ensure all focusable elements have a visible :focus style (outline or equivalent)"
            ))
        
        return issues
    
    async def cleanup_async(self) -> None:
        """Async cleanup of browser resources."""
        try:
            if self.context:
                await self.context.close()
                self.context = None
            if self.browser:
                await self.browser.close()
                self.browser = None
            if self.playwright:
                await self.playwright.stop()
                self.playwright = None
        except Exception:
            pass
    
    def cleanup(self) -> None:
        """Cleanup browser resources (sync wrapper)."""
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.create_task(self.cleanup_async())
            else:
                loop.run_until_complete(self.cleanup_async())
        except Exception:
            pass

