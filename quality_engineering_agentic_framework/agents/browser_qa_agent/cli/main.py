import asyncio
import json
import typer
from rich.console import Console
from rich.table import Table
from rich import print as rprint

app = typer.Typer(help="QA Browser Agent CLI")
console = Console()


@app.command()
def run(
    url: str = typer.Argument(..., help="URL to test"),
    test: str = typer.Argument(..., help="Natural language test description"),
    max_steps: int = typer.Option(30, help="Max agent steps"),
    headless: bool = typer.Option(True, help="Run browser headless"),
    output: str = typer.Option("report.html", help="Output HTML report path"),
    platform: str = typer.Option("web", help="Platform: web | mobile_web | mobile_native"),
    device: str = typer.Option("iphone_14", help="Mobile device preset (for mobile_web)"),
    provider: str = typer.Option("", help="LLM provider override: anthropic|openai|gemini|ollama"),
    model: str = typer.Option("", help="LLM model override"),
):
    """Run a QA test directly (no server needed)."""
    from ..llm import LLMClient
    from ..planner import QAPlanner
    from ..reporter import Reporter
    from ..storage import get_storage
    import uuid

    run_id = str(uuid.uuid4())
    console.print(f"[bold blue]Starting QA run[/bold blue] {run_id}")
    console.print(f"URL: {url}")
    console.print(f"Test: {test}")

    async def _run():
        from ..providers import get_provider
        storage = get_storage()
        if provider:
            p = get_provider(provider, **_provider_kwargs(provider, model))
            from ..llm import LLMClient as _LC
            llm = _LC(provider=p)
        else:
            llm = LLMClient()
        mobile_config = {"device": device} if platform == "mobile_web" else {}
        planner = QAPlanner(llm=llm, storage=storage, max_steps=max_steps, headless=headless, platform=platform, mobile_config=mobile_config)
        reporter = Reporter(storage=storage)

        with console.status("Agent running..."):
            result = await planner.run(run_id=run_id, base_url=url, nl_description=test)

        report_data = await reporter.generate(run_id=run_id, result=result)
        return result, report_data

    result, report_data = asyncio.run(_run())

    status_color = "green" if result.status == "passed" else "red"
    console.print(f"\nStatus: [{status_color}]{result.status.upper()}[/{status_color}]")
    console.print(f"Bugs found: {report_data['bugs_found']}")
    console.print(f"Summary: {result.summary}")

    if report_data["findings"]:
        table = Table(title="Findings")
        table.add_column("Severity")
        table.add_column("Title")
        table.add_column("Expected")
        table.add_column("Actual")
        for f in report_data["findings"]:
            table.add_row(f["severity"], f["title"], f.get("expected", ""), f.get("actual", ""))
        console.print(table)

    console.print(f"\nReport: {report_data['html_report_url']}")


@app.command()
def serve(
    host: str = typer.Option("0.0.0.0", help="Host"),
    port: int = typer.Option(8080, help="Port"),
    reload: bool = typer.Option(False, help="Auto-reload"),
):
    """Start the QA Agent API server."""
    import uvicorn
    uvicorn.run(
        "quality_engineering_agentic_framework.agents.browser_qa_agent.api.main:app",
        host=host,
        port=port,
        reload=reload,
    )


@app.command()
def worker():
    """Start a Celery worker."""
    from ..workers.celery_app import celery_app
    celery_app.worker_main(["worker", "--loglevel=info", "--concurrency=2"])


def _provider_kwargs(provider: str, model: str) -> dict:
    import os
    kwargs = {}
    if model:
        kwargs["model"] = model
    if provider == "anthropic":
        kwargs.setdefault("api_key", os.getenv("ANTHROPIC_API_KEY", ""))
    elif provider in ("openai", "azure_openai"):
        kwargs.setdefault("api_key", os.getenv("OPENAI_API_KEY", ""))
    elif provider == "gemini":
        kwargs.setdefault("api_key", os.getenv("GEMINI_API_KEY", ""))
    return kwargs


if __name__ == "__main__":
    app()
