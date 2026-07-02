"""
QEAF MCP Server

Exposes all Quality Engineering Agentic Framework capabilities as MCP tools.
Any MCP-compatible AI client (Claude Desktop, VS Code Copilot, Cursor, Windsurf)
can use these tools directly from a conversation.

Usage:
    python mcp_server.py

The standalone_automation tool runs generation on the MCP HOST's model via
sampling (no key/token in this server). If the host does not support sampling,
it falls back automatically to the GITHUB_TOKEN-based Copilot provider.

Environment variables:
    LLM_PROVIDER       - openai | gemini | copilot  (default: copilot)
    LLM_MODEL          - model name                  (default: gpt-4o)
    LLM_TEMPERATURE    - 0.0 to 1.0                  (default: 0.2)
    LLM_MAX_TOKENS     - max response tokens          (default: 8000)
    OPENAI_API_KEY     - required when provider=openai
    GEMINI_API_KEY     - required when provider=gemini
    GITHUB_TOKEN       - required when provider=copilot; also used as the
                         fallback for standalone_automation if the host
                         cannot sample (otherwise no key is needed)
"""

import os
import json
from typing import Optional, Any, List

from mcp.server.fastmcp import FastMCP, Context

from quality_engineering_agentic_framework.llm.llm_factory import LLMFactory
from quality_engineering_agentic_framework.llm.copilot_llm import CopilotLLM
from quality_engineering_agentic_framework.llm.llm_interface import LLMInterface
from quality_engineering_agentic_framework.llm.sampling_llm import SamplingLLM, SamplingNotSupportedError
from quality_engineering_agentic_framework.agents.automation_agent import AutomationAgent
from quality_engineering_agentic_framework.agents.test_analyser_agent import TestAnalyserAgent, SUPPORTED_FORMATS
from quality_engineering_agentic_framework.utils.logger import get_logger
from quality_engineering_agentic_framework.utils.code_validation import validate_and_format

from mcp_tool_flags import is_tool_enabled, enabled_tools

from pydantic import BaseModel, Field

logger = get_logger(__name__)

mcp = FastMCP("QEAF")


def tool_if_enabled(name: str):
    """
    Decorator that registers a tool only when its feature flag is on
    (see mcp_tool_flags.py). Disabled tools are skipped entirely and never
    appear in the client's tool list.
    """
    if is_tool_enabled(name):
        return mcp.tool()

    def _skip(fn):
        logger.info(f"MCP tool '{name}' is disabled by flag — not registered.")
        return fn

    return _skip


class _SamplingWithTokenFallbackLLM(LLMInterface):
    """
    Prefers MCP host sampling (no keys). If the connected host does not support
    sampling, transparently falls back — once — to the token-based provider from
    _build_llm() (CopilotLLM / GITHUB_TOKEN). The agent stays provider-agnostic.
    """

    def __init__(self, ctx: Any):
        self._primary = SamplingLLM(ctx)
        self._fallback: Optional[LLMInterface] = None

    def _get_fallback(self) -> LLMInterface:
        if self._fallback is None:
            logger.warning(
                "MCP host does not support sampling — falling back to token-based provider."
            )
            self._fallback = _build_llm()
        return self._fallback

    async def generate(self, *args, **kwargs) -> str:
        if self._fallback is not None:
            return await self._fallback.generate(*args, **kwargs)
        try:
            return await self._primary.generate(*args, **kwargs)
        except SamplingNotSupportedError:
            return await self._get_fallback().generate(*args, **kwargs)

    async def generate_with_json_output(self, *args, **kwargs):
        if self._fallback is not None:
            return await self._fallback.generate_with_json_output(*args, **kwargs)
        try:
            return await self._primary.generate_with_json_output(*args, **kwargs)
        except SamplingNotSupportedError:
            return await self._get_fallback().generate_with_json_output(*args, **kwargs)

    def get_provider_name(self) -> str:
        return self._fallback.get_provider_name() if self._fallback else "sampling"


def _build_llm():
    """
    Build an LLM instance from environment variables.

    For the MCP server, 'copilot' is handled directly via CopilotLLM
    (bypassing LLMFactory so it stays out of the UI dropdown).
    openai and gemini go through the shared LLMFactory as normal.
    """
    provider = os.environ.get("LLM_PROVIDER", "copilot").lower()

    config = {
        "provider": provider,
        "model": os.environ.get("LLM_MODEL", "gpt-4o"),
        "temperature": float(os.environ.get("LLM_TEMPERATURE", "0.2")),
        "max_tokens": int(os.environ.get("LLM_MAX_TOKENS", "8000")),
    }

    if provider == "copilot":
        github_token = os.environ.get("GITHUB_TOKEN", "")
        if not github_token:
            raise ValueError(
                "GITHUB_TOKEN is not set. "
                "Set it in the MCP server env config to your GitHub Personal Access Token."
            )
        config["api_key"] = github_token
        config["base_url"] = os.environ.get(
            "COPILOT_BASE_URL", "https://models.inference.ai.azure.com"
        )
        # OpenAI key passed only for RAG embeddings — Copilot still handles the LLM
        config["openai_api_key"] = os.environ.get("OPENAI_API_KEY", "")
        return CopilotLLM(config)

    elif provider == "openai":
        api_key = os.environ.get("OPENAI_API_KEY", "")
        if not api_key:
            raise ValueError("OPENAI_API_KEY is not set")
        config["api_key"] = api_key

    elif provider == "gemini":
        api_key = os.environ.get("GEMINI_API_KEY", "")
        if not api_key:
            raise ValueError("GEMINI_API_KEY is not set")
        config["api_key"] = api_key

    else:
        raise ValueError(
            f"Unsupported LLM_PROVIDER '{provider}'. Use: copilot, openai, gemini"
        )

    return LLMFactory.create_llm(config)


# ---------------------------------------------------------------------------
# Tool 1 — Generate Test Cases
# ---------------------------------------------------------------------------

async def _resolve_project_path(ctx: Context, project_path: Optional[str]) -> Optional[str]:
    """
    Resolve the project to operate on. If the caller didn't pass project_path,
    ask the MCP host for its workspace roots (VS Code exposes the open folder)
    and use the first root. Falls back to None if roots aren't available.
    """
    if project_path:
        return project_path
    try:
        result = await ctx.session.list_roots()
        roots = result.roots or []
        if roots:
            from urllib.parse import urlparse, unquote
            uri = str(roots[0].uri)
            resolved = unquote(urlparse(uri).path) if uri.startswith("file://") else uri
            logger.info(f"Auto-detected project_path from workspace root: {resolved}")
            return resolved
        logger.warning("Host returned no workspace roots.")
    except Exception as e:
        logger.warning(f"Could not get workspace roots from host: {e}")
    return None


class FileInput(BaseModel):
    """One existing project file passed in by the client (agent-mediated mode)."""
    path: str = Field(description="Relative path of the file within the project")
    content: str = Field(description="Full text content of the file")


class _WriteConfirm(BaseModel):
    """Human-in-the-loop: confirm before writing generated files to disk."""
    write: bool = Field(default=False, description="Write the generated files into the project now? (may overwrite existing files)")


def _missing_context(file_map: Optional[dict]) -> List[str]:
    """For REMOTE (agent-fed) mode: if the project looks established but the key
    reuse/style files weren't passed in, list what the assistant should fetch
    (with its codebase tools) and re-call with — instead of degrading silently."""
    if not file_map:
        return []
    names = [os.path.basename(p).lower() for p in file_map]
    established = any(
        n in ("package.json", "pom.xml", "requirements.txt", "pyproject.toml",
              "build.gradle", "cypress.config.js", "playwright.config.ts",
              "playwright.config.js") or n.endswith(".csproj")
        for n in names
    )
    if not established:
        return []  # likely greenfield — best-practice standards path, no request
    missing = []
    if not any(("test" in n or "spec" in n) for n in names):
        missing.append("an existing test/spec file (to match your test style exactly)")
    reuse_hint = ("page", "locator", "selector", "client", "helper", "fixture", "base", "util")
    if not any(any(k in n for k in reuse_hint) for n in names):
        missing.append("the page object(s)/helpers/locators the test should reuse")
    return missing


class _UiInfo(BaseModel):
    """Details needed to generate UI automation."""
    app_url: str = Field(default="", description="Base URL of the web app under test")
    browser: str = Field(default="chrome", description="Browser: chrome | firefox | edge")


class _ApiInfo(BaseModel):
    """Details needed to generate API automation."""
    api_base_url: str = Field(default="", description="Base URL of the API under test")
    auth: str = Field(default="none", description="Auth type: none | bearer | basic | apikey")


async def _maybe_elicit(ctx, automation_type, app_url, browser, api_base_url, auth):
    """
    Ask the user (via MCP elicitation) for missing UI/API details instead of
    guessing. Best-effort: if the host doesn't support elicitation, or the user
    declines/cancels, we proceed with whatever was provided plus defaults.
    """
    atype = (automation_type or "ui").lower()
    needs_ui = atype in ("ui", "both")
    needs_api = atype in ("api", "both")
    try:
        if needs_ui and not app_url:
            res = await ctx.elicit(
                "UI automation: what is the app URL and which browser?", _UiInfo
            )
            if res.action == "accept" and res.data:
                app_url = res.data.app_url or app_url
                browser = res.data.browser or browser
        if needs_api and not api_base_url:
            res = await ctx.elicit(
                "API automation: what is the API base URL and auth type?", _ApiInfo
            )
            if res.action == "accept" and res.data:
                api_base_url = res.data.api_base_url or api_base_url
                auth = res.data.auth or auth
    except Exception as e:
        logger.warning(f"Elicitation unavailable; proceeding with defaults: {e}")
    return app_url, browser, api_base_url, auth


# ---------------------------------------------------------------------------
# Tool 6 — Standalone Automation (host-sampled, key-free)
# ---------------------------------------------------------------------------

@tool_if_enabled("standalone_automation")
async def standalone_automation(
    ctx: Context,
    instructions: str,
    project_path: Optional[str] = None,
    automation_type: str = "ui",
    language: Optional[str] = None,
    framework: Optional[str] = None,
    browser: str = "chrome",
    rendered_dom: Optional[str] = None,
    api_base_url: Optional[str] = None,
    api_endpoint: Optional[str] = None,
    api_method: Optional[str] = None,
    app_url: Optional[str] = None,
    auth: Optional[str] = None,
    apply: bool = False,
    existing_files: Optional[List[FileInput]] = None,
    config_text: Optional[str] = None,
    heal: bool = True,
) -> str:
    """
    Generate automation scripts for ANY framework — UI or API — that fit an
    EXISTING automation project and reuse its existing methods.

    BEFORE CALLING (assistant): use your codebase tools (search/LSP/navigation) to
    gather the files this needs to match the team's standards, and pass them in
    `existing_files`:
      • the page object(s)/helpers/API client the test should reuse,
      • the locator/selector module and the test-data module,
      • ONE existing test/spec (so the style is matched exactly),
      • config like .env / *.config.* / package.json (for module system + base URL).
    The more accurate the files you pass, the higher the fidelity.

    REVIEW-FIRST: by default this tool does NOT write files. It returns them and
    the assistant should apply each one via the editor so the USER reviews a diff
    and chooses Allow/Skip before any change lands. (Only `apply: true` writes
    directly, for headless automation with no human review.)

    Generation runs on the MCP host's model via sampling (no API key/token in
    this server). If the host doesn't support sampling, it falls back to the
    GITHUB_TOKEN-based Copilot provider.

    TWO MODES — works whether this server is local or remote:

      • LOCAL server (same machine as the repo): omit existing_files. The server
        reads project_path from disk — detects language/framework, learns the
        layout, extracts existing methods — and (with apply:true) writes files
        back to disk.

      • REMOTE server (cloud / different machine): the server CANNOT read your
        disk. So, in agent mode, FIRST gather the relevant existing files from
        the workspace (page objects, base classes, API clients, utils, and
        config like .env / *.config.*) and pass them in `existing_files`; the
        server reuses them and RETURNS the generated files — then YOU (the
        assistant) write each returned file to its path in the workspace.

    Args:
        instructions:    Test cases (JSON from generate_test_cases) or plain text.
        project_path:    Absolute path to the framework (LOCAL server only). Optional —
                         auto-detected from the host workspace (MCP roots) if omitted.
        automation_type: ui | api | both (default: ui).
        language:        Override detected language (python | java | javascript | c#).
        framework:       Override detected framework (selenium, playwright, cypress,
                         restassured, requests, supertest, ...). Auto-detected if empty.
        browser:         Browser for UI — chrome | firefox | edge (default: chrome).
        rendered_dom:    Optional HTML of the page under test (UI locators).
        api_base_url:    Optional API base URL (api/both). Prompted if missing.
        api_endpoint:    Optional API endpoint path (api/both).
        api_method:      Optional HTTP method — GET | POST | PUT | DELETE | PATCH.
        app_url:         Optional web app base URL (ui/both). Prompted if missing.
        auth:            Optional API auth type — none | bearer | basic | apikey.
        apply:           Default FALSE (recommended). When false, the tool RETURNS the
                         files and the assistant applies them via the editor, so the
                         USER sees a diff and Allow/Skip for EACH change before it lands.
                         Set true ONLY for headless/local automation with no human
                         review — it writes straight to disk (LOCAL server, no diff).
        existing_files:  REMOTE mode — list of {path, content} for the project's
                         relevant existing files, so the server can reuse them
                         without disk access.
        config_text:     REMOTE mode — optional concatenated config/.env text to
                         discover base URL / auth from.
        heal:            If true (default), self-heal Phase 1 — after generating,
                         statically check each file (syntax/parse) and auto-fix any
                         load-time errors (up to 2 passes). No browser/app/run
                         needed; makes extra model calls ONLY when a file is broken.

    Returns:
        A report (mode, validation, write results) followed by the generated
        files as code blocks, one per file with its relative path.
    """
    # Normalize client-supplied files (REMOTE/agent-mediated mode).
    file_map = {f.path: f.content for f in existing_files} if existing_files else None

    logger.info("=" * 70)
    logger.info(
        f"▶ standalone_automation CALLED | type={automation_type} apply={apply} "
        f"heal={heal} remote_files={len(file_map) if file_map else 0}"
    )

    # Auto-detect the project from the host's workspace when not provided.
    project_path = await _resolve_project_path(ctx, project_path)
    mode_label = ("remote/agent-fed" if file_map else
                  "local-disk" if (project_path and os.path.isdir(project_path)) else "generic")
    logger.info(f"  ├─ project: {project_path or '(none)'} | mode: {mode_label}")

    # Discover base URL / auth already defined in the project's config, so we
    # only have to ask when they genuinely don't exist (e.g. a new framework).
    # Use the supplied files/text when remote; otherwise read disk.
    if file_map or config_text:
        discovered = AutomationAgent.discover_config(
            files=file_map, config_text=config_text or "")
    else:
        discovered = AutomationAgent.discover_config(project_path=project_path)
    logger.info(
        f"  ├─ discovered config: base_url={discovered.get('base_url') or '-'} "
        f"auth={discovered.get('auth') or '-'}"
    )
    if not app_url:
        app_url = discovered.get("base_url", "")
    if not api_base_url:
        api_base_url = discovered.get("base_url", "")
    if not auth:
        auth = discovered.get("auth", "")

    # Ask the user only for UI/API details STILL missing after discovery.
    app_url, browser, api_base_url, auth = await _maybe_elicit(
        ctx, automation_type, app_url, browser, api_base_url, auth
    )
    logger.info(
        f"  ├─ inputs: app_url={app_url or '-'} api_base_url={api_base_url or '-'} "
        f"auth={auth or '-'} browser={browser}"
    )

    # Accept both JSON test cases and plain text
    try:
        test_cases: Any = json.loads(instructions)
        if isinstance(test_cases, dict) and "test_cases" in test_cases:
            test_cases = test_cases["test_cases"]
    except (json.JSONDecodeError, TypeError):
        test_cases = instructions

    api_details = None
    if api_base_url or api_endpoint or auth:
        api_details = {
            "base_url": api_base_url or "",
            "endpoint": api_endpoint or "",
            "method": (api_method or "GET").upper(),
            "auth": auth or "none",
        }

    llm = _SamplingWithTokenFallbackLLM(ctx)
    agent = AutomationAgent(llm, {
        "automation_type": automation_type,
        "language": language,
        "framework": framework,
        "browser": browser,
    })

    logger.info("  ├─ generating (host sampling, key-free; token fallback if needed)…")
    result = await agent.process(
        test_cases,
        project_path=project_path,
        existing_files=file_map,
        rendered_dom=rendered_dom,
        api_details=api_details,
        app_url=app_url,
    )
    logger.info(
        f"  ├─ generated {len(result)} file(s) via '{llm.get_provider_name()}': "
        f"{', '.join(list(result.keys())[:6])}"
    )

    # Post-generation: self-heal (Phase 1) static load-time errors, then the
    # report reflects the healed files. Heal makes NO extra model calls when the
    # generated code is already clean.
    heal_log: List[str] = []
    if heal:
        result, validation, heal_log = await agent.heal_static(result, max_attempts=2)
        for line in heal_log:
            logger.info(f"  │   heal: {line}")
    else:
        result, validation = validate_and_format(result)
    bad = [e["file"] for e in validation if not e.get("ok", True)]
    logger.info(f"  ├─ validation: {len(validation)} file(s) checked"
                + (f" | still failing: {bad}" if bad else " | all OK"))

    # Write files only when the server can reach disk (LOCAL) AND the user
    # confirms. Default apply=false means nothing is written.
    server_can_write = bool(apply and project_path and os.path.isdir(project_path))
    write_report = None
    write_declined = False
    if server_can_write:
        confirmed = True
        logger.info(f"  ├─ apply=true → asking user to confirm writing {len(result)} file(s)…")
        try:
            res = await ctx.elicit(
                f"Write {len(result)} generated file(s) into {project_path}? "
                "This may overwrite existing files.",
                _WriteConfirm,
            )
            if res.action == "accept" and res.data:
                confirmed = bool(res.data.write)
            else:
                confirmed = False
        except Exception as e:
            logger.warning(f"  │   write-confirm prompt unavailable; honoring apply=true ({e})")
            confirmed = True  # explicit apply flag stands when host can't prompt
        if confirmed:
            logger.info("  ├─ write CONFIRMED → writing to disk")
            write_report = AutomationAgent.write_files(result, project_path)
            for entry in write_report:
                logger.info(f"  │   {entry['status']}: {entry['file']}")
        else:
            logger.info("  ├─ write DECLINED by user → returning as preview")
            server_can_write = False
            write_declined = True

    # ---- Build the response ----
    if server_can_write:
        mode = "APPLIED (written directly by server — no editor diff)"
    else:
        mode = "REVIEW & APPLY (assistant applies each file; user sees diff + Allow/Skip)"
    logger.info(f"  └─ done | files={len(result)} | mode={mode}")

    header = [
        f"**Standalone automation** — {mode}",
        f"Project: {project_path or '(none — generic output)'}",
        f"Type: {automation_type}",
    ]

    heal_lines = []
    if heal_log:
        heal_lines = ["", "**Self-heal (static checks):**"] + [f"- {x}" for x in heal_log]

    val_lines = ["", "**Validation:**"]
    for entry in validation:
        mark = "" if entry.get("ok", True) else " ⚠️"
        val_lines.append(f"- `{entry['file']}`{mark} — {', '.join(entry['checks'])}")

    # #2 — Request missing context (leverages Copilot's codebase navigation).
    context_lines = []
    missing = _missing_context(file_map)
    if missing:
        context_lines = ["", "**⚠️ For higher fidelity, please provide more context and re-call:**"]
        context_lines += [f"- {m}" for m in missing]
        context_lines += ["Use your codebase tools to fetch these, add them to `existing_files`, "
                          "and call `standalone_automation` again. (A best-effort draft is below.)"]

    # #3 — Verification handoff (leverages Copilot's LSP/codebase grounding).
    VERIFY_BLOCK = [
        "", "**Before applying, verify against the real codebase (assistant):**",
        "- Confirm every called method/class actually exists in the workspace; fix any that don't.",
        "- Correct import/require paths to the real file locations.",
        "- Confirm referenced fixtures/selectors/test-data exist.",
    ]

    APPLY_INSTRUCTION = (
        "**Then apply each file** by creating/updating it at its relative path using your editor "
        "edit tool — so the USER sees a diff and can **Allow or Skip each change**. Never write silently."
    )
    write_lines = []
    if write_report is not None:
        write_lines = ["", "**Write results (written directly by server — no editor diff):**"]
        for entry in write_report:
            write_lines.append(f"- `{entry['file']}` — {entry['status']} ({entry.get('detail','')})")
    else:
        # Default / preview / remote: verify, then apply with review.
        write_lines = VERIFY_BLOCK + ["", APPLY_INSTRUCTION]
        if write_declined:
            write_lines = ["", "_Write declined._"] + write_lines

    file_blocks = ["", "**Files:**"]
    for filename, code in result.items():
        file_blocks.append(f"### {filename}\n```\n{code}\n```")

    if not result:
        return "\n".join(header) + "\n\nNo files generated."
    return "\n".join(header + context_lines + heal_lines + val_lines + write_lines + file_blocks)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logger.info(f"Enabled MCP tools: {enabled_tools()}")
    print(f"Enabled MCP tools: {enabled_tools()}")
    transport = os.environ.get("MCP_TRANSPORT", "stdio")
    if transport == "sse":
        import uvicorn
        host = os.environ.get("MCP_HOST", "0.0.0.0")
        port = int(os.environ.get("MCP_PORT", "8080"))
        print(f"Starting QEAF MCP server at http://{host}:{port}/sse")
        app = mcp.sse_app()
        uvicorn.run(app, host=host, port=port)
    else:
        mcp.run(transport="stdio")
