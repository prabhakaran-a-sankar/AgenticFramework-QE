"""Command-line interface for the Intelligent Accessibility Assistant."""

import asyncio
from pathlib import Path
from typing import Optional
import typer
from rich.console import Console
from rich.table import Table
from quality_engineering_agentic_framework.iaa.core.engine import AccessibilityEngine
from quality_engineering_agentic_framework.iaa.core.models import Severity
from quality_engineering_agentic_framework.iaa.modules.web import WebAccessibilityModule
from quality_engineering_agentic_framework.iaa.modules.ai.enhancer import AIEnhancer
from quality_engineering_agentic_framework.iaa.reporters.json_reporter import JSONReporter
from quality_engineering_agentic_framework.iaa.reporters.html_reporter import HTMLReporter

app = typer.Typer(
    name="iaa",
    help="Intelligent Accessibility Assistant - AI-enhanced accessibility testing",
    add_completion=False
)
console = Console()


@app.command()
def test(
    target: str = typer.Argument(..., help="URL or path to test"),
    output_format: str = typer.Option("html", "--format", "-f", help="Output format: json, html, markdown"),
    output_path: Optional[Path] = typer.Option(None, "--output", "-o", help="Output file path"),
    ai_enabled: bool = typer.Option(True, "--ai-enabled/--no-ai", help="Enable AI enhancements"),
    offline_ai: bool = typer.Option(True, "--offline-ai/--online-ai", help="Use offline AI mode"),
    fail_on: str = typer.Option("critical", "--fail-on", help="Fail on severity: critical, serious, moderate, minor"),
    fail_threshold: int = typer.Option(0, "--fail-threshold", help="Fail if issue count exceeds threshold"),
    headless: bool = typer.Option(True, "--headless/--headed", help="Run browser in headless mode"),
) -> None:
    """Run accessibility tests on a target URL or application."""
    
    console.print(f"[bold blue]Testing:[/bold blue] {target}")
    console.print(f"[dim]AI Enhancement: {'Enabled (Offline)' if ai_enabled and offline_ai else 'Enabled (Online)' if ai_enabled else 'Disabled'}[/dim]\n")
    
    # Initialize modules
    web_module = WebAccessibilityModule(config={"headless": headless})
    engine = AccessibilityEngine(modules=[web_module])
    
    # Run tests
    try:
        result = asyncio.run(engine.execute(target))
    except Exception as e:
        console.print(f"[bold red]ERROR:[/bold red] {e}")
        raise typer.Exit(code=2)
    
    # AI enhancement
    if ai_enabled:
        enhancer = AIEnhancer(offline=offline_ai, enabled=True)
        result.issues = asyncio.run(enhancer.enhance_issues(result.issues))
    
    # Display summary
    _display_summary(result)
    
    # Generate report
    if output_format == "json":
        reporter = JSONReporter()
        output = reporter.generate(result, output_path)
        if not output_path:
            console.print(output)
    elif output_format == "html":
        reporter = HTMLReporter()
        if not output_path:
            output_path = Path("accessibility-report.html")
        reporter.generate(result, output_path)
        console.print(f"\n[bold green]OK[/bold green] Report saved to: {output_path}")
    
    # Check exit conditions
    exit_code = _check_exit_conditions(result, fail_on, fail_threshold)
    if exit_code != 0:
        console.print(f"\n[bold red]FAILED[/bold red] Test failed")
        raise typer.Exit(code=exit_code)
    
    console.print(f"\n[bold green]PASSED[/bold green] Test passed")


def _display_summary(result) -> None:
    """Display test summary in the console."""
    table = Table(title="Accessibility Test Summary", show_header=True)
    table.add_column("Severity", style="bold")
    table.add_column("Count", justify="right")
    
    table.add_row("Critical", f"[red]{result.critical_count}[/red]")
    table.add_row("Serious", f"[yellow]{result.serious_count}[/yellow]")
    table.add_row("Moderate", f"[blue]{result.moderate_count}[/blue]")
    table.add_row("Minor", f"[green]{result.minor_count}[/green]")
    table.add_row("Total", f"[bold]{result.total_issues}[/bold]")
    
    console.print(table)


def _check_exit_conditions(result, fail_on: str, fail_threshold: int) -> int:
    """Check if test should fail based on conditions."""
    severity_map = {
        "critical": result.critical_count,
        "serious": result.serious_count + result.critical_count,
        "moderate": result.moderate_count + result.serious_count + result.critical_count,
        "minor": result.total_issues
    }
    
    count = severity_map.get(fail_on.lower(), 0)
    
    if count > fail_threshold:
        return 1
    
    return 0


@app.command()
def version() -> None:
    """Show version information."""
    console.print("[bold]Intelligent Accessibility Assistant[/bold]")
    console.print("Version: 0.1.0")


if __name__ == "__main__":
    app()

