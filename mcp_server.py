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

import base64
import os
import sys
import json
import tempfile
from datetime import datetime
from typing import Optional, Any, List

from mcp.server.fastmcp import FastMCP, Context
from mcp.types import (
    CallToolResult, ClientCapabilities, SamplingCapability, TextContent, ToolAnnotations,
)

from quality_engineering_agentic_framework.llm.llm_factory import LLMFactory
from quality_engineering_agentic_framework.llm.copilot_llm import CopilotLLM
from quality_engineering_agentic_framework.llm.llm_interface import LLMInterface
from quality_engineering_agentic_framework.llm.sampling_llm import SamplingLLM, SamplingNotSupportedError
from quality_engineering_agentic_framework.agents.automation_agent import AutomationAgent
from quality_engineering_agentic_framework.agents.test_analyser_agent import TestAnalyserAgent, SUPPORTED_FORMATS
from quality_engineering_agentic_framework.utils.logger import get_logger
from quality_engineering_agentic_framework.utils.code_validation import validate_and_format

from quality_engineering_agentic_framework.utils.reuse_catalog import (
    build_catalog, check_calls, load_project_files,
)

from mcp_tool_flags import is_tool_enabled, enabled_tools

from pydantic import BaseModel, Field

logger = get_logger(__name__)

mcp = FastMCP("QEAF")


def tool_if_enabled(name: str, **tool_kwargs):
    """
    Decorator that registers a tool only when its feature flag is on
    (see mcp_tool_flags.py). Disabled tools are skipped entirely and never
    appear in the client's tool list.
    """
    if is_tool_enabled(name):
        return mcp.tool(**tool_kwargs)

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


def _fallback_available() -> bool:
    """True if a key/token-based provider is configured, i.e. the server can
    generate code itself when the host cannot sample."""
    provider = os.environ.get("LLM_PROVIDER", "copilot").lower()
    key = {"copilot": "GITHUB_TOKEN", "openai": "OPENAI_API_KEY",
           "gemini": "GEMINI_API_KEY"}.get(provider)
    return bool(key and os.environ.get(key))


def _result(text: str, **data: Any) -> CallToolResult:
    """Return the human-readable report unchanged (what clients show the model today)
    plus the same information as machine-readable structuredContent (CI, scripts).
    `result` repeats the text so the payload is a superset of the shape older versions
    returned ({"result": "<text>"}) — clients reading that key keep working."""
    return CallToolResult(content=[TextContent(type="text", text=text)],
                          structuredContent={"result": text, **data})


def _redaction_note(agent: Any) -> str:
    n = getattr(agent, "last_redactions", 0)
    if not n:
        return ""
    return (f"\n\n_{n} secret-like value(s) were masked in the context sent to the model "
            f"(set QEAF_REDACT_SECRETS=false to disable)._")


def _reuse_report_lines(report: Optional[dict]) -> List[str]:
    """What the model said it reused / created (empty when it gave no report)."""
    if not report or not (report.get("reused") or report.get("created")):
        return []
    lines = ["", "**Reuse report (from the model):**"]
    lines += [f"- ♻️ reused {x}" for x in report.get("reused", [])]
    lines += [f"- ➕ created {x}" for x in report.get("created", [])]
    return lines


def _reuse_check_lines(findings: List[dict], checked: bool = True) -> List[str]:
    """Warnings for calls to methods that exist nowhere (empty when nothing to say)."""
    if not checked:
        return []
    if not findings:
        return ["", "Reuse check: every call to a known class resolves to an existing or newly "
                    "added method. ✅"]
    lines = ["", "**⚠️ Reuse check — calls to methods that don't exist:**"]
    for f in findings:
        hint = f" Similar existing: {', '.join(f['suggestions'])}." if f.get("suggestions") else ""
        lines.append(f"- `{f['file']}:{f['line']}` {f['message']}{hint}")
    lines.append("Reuse an existing method, or add the missing one to its class, then re-check.")
    return lines


def _allowed_roots() -> List[str]:
    """Optional allow-list of project folders (QEAF_ALLOWED_ROOTS, separated by
    os.pathsep). Empty/unset = no restriction, i.e. today's behaviour."""
    raw = os.environ.get("QEAF_ALLOWED_ROOTS", "")
    return [os.path.realpath(os.path.expanduser(p.strip()))
            for p in raw.split(os.pathsep) if p.strip()]


def _path_not_allowed(project_path: Optional[str]) -> Optional[str]:
    """Return a refusal message if an allow-list is set and project_path is outside
    it; otherwise None. Resolves symlinks and '..' before comparing."""
    roots = _allowed_roots()
    if not roots or not project_path:
        return None
    real = os.path.realpath(os.path.expanduser(project_path))
    for root in roots:
        try:
            if os.path.commonpath([real, root]) == root:
                return None
        except ValueError:  # different drives (Windows)
            continue
    return (f"Refused: '{project_path}' is outside the folders this QEAF server is allowed "
            f"to use (QEAF_ALLOWED_ROOTS). Allowed: {', '.join(roots)}")


def _host_can_sample(ctx: Any) -> bool:
    """Whether the connected host advertised MCP sampling. If we can't tell,
    assume yes so the existing behaviour is unchanged."""
    try:
        return bool(ctx.session.check_client_capability(
            ClientCapabilities(sampling=SamplingCapability())))
    except Exception as e:
        logger.warning(f"Could not read host sampling capability; assuming supported: {e}")
        return True


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

# Short description sent to the client on every session (keeps token cost low).
# The full parameter reference lives in the docstring below and in the README.
_STANDALONE_DESCRIPTION = (
    "Generate UI/API test automation that fits an EXISTING project and reuses its methods. "
    "Review-first: returns the files and never writes to disk unless apply=true.\n"
    "Before calling: gather the page objects/helpers, locators, test data, ONE existing test "
    "and config (package.json, .env) and pass them as existing_files [{path, content}] — "
    "better files give better fidelity. If the server runs on the same machine as the repo, "
    "omit existing_files and pass project_path.\n"
    "Key args: instructions (test cases JSON or plain text); automation_type ui|api|both; "
    "language/framework (auto-detected); app_url/api_base_url/auth (discovered from config, "
    "else asked); heal (auto-fix syntax errors); apply (write to disk, local only); "
    "prepare_only (return a brief for YOU to write the code).\n"
    "If the result is a brief (HOST-GENERATES MODE): write the files from it, check them "
    "with validate_generated_code, then apply them via the editor so the user reviews each diff."
)


@tool_if_enabled(
    "standalone_automation",
    description=_STANDALONE_DESCRIPTION,
    annotations=ToolAnnotations(
        title="Generate test automation",
        readOnlyHint=False,      # can write files when apply=true
        destructiveHint=True,    # ...and those writes may overwrite existing files
        idempotentHint=False,    # model output varies run to run
        openWorldHint=True,      # may call a model API when a fallback key is configured
    ),
)
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
    prepare_only: bool = False,
) -> CallToolResult:
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
        prepare_only:    If true — or automatically when the host cannot sample AND no
                         fallback key/token is configured — the server makes NO model
                         call. It returns the full grounded brief (existing source,
                         style contract, standards, task) and the assistant writes the
                         files itself, then checks them with validate_generated_code.

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
    refusal = _path_not_allowed(project_path)
    if refusal:
        logger.warning(f"  └─ {refusal}")
        return _result(refusal, mode="refused", project=project_path)
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

    # Host cannot sample and there is no key/token to fall back on: the server has
    # no model to call, so return the grounded brief and let the assistant write it.
    if not prepare_only and not _host_can_sample(ctx) and not _fallback_available():
        logger.info("  ├─ host has no sampling and no fallback key → host-generates mode")
        prepare_only = True

    if prepare_only:
        brief = await agent.process(
            test_cases,
            project_path=project_path,
            existing_files=file_map,
            rendered_dom=rendered_dom,
            api_details=api_details,
            app_url=app_url,
            prepare_only=True,
        )
        validate_step = (
            "3. Call the `validate_generated_code` tool with the files you wrote"
            + (f" and project_path=\"{project_path}\"" if project_path and os.path.isdir(project_path) else "")
            + " — it also flags calls to methods that don't exist — and fix any reported problems."
            if is_tool_enabled("validate_generated_code")
            else "3. Re-read each file once for syntax errors before applying."
        )
        logger.info(f"  └─ done | mode=HOST-GENERATES | brief={len(brief['__prompt__'])} chars")
        text = "\n".join([
            "**Standalone automation** — HOST-GENERATES MODE (the server has no model here)",
            f"Project: {project_path or '(none — generic output)'}",
            f"Type: {automation_type}",
            "",
            "The server has no model of its own in this setup, so YOU (the assistant) write the "
            "code from the brief below. Follow every rule in it exactly.",
            "",
            "── BRIEF ──",
            f"SYSTEM: {brief['__system__']}",
            "",
            brief["__prompt__"],
            "── END BRIEF ──",
            "",
            "**Next (assistant):**",
            "1. Write each file as the brief specifies — full, runnable, no placeholders.",
            "2. Verify every method/class/import you use exists in the workspace; fix any that don't.",
            validate_step,
            "4. Apply each file via your editor edit tool so the USER sees a diff and can "
            "**Allow or Skip each change**. Never write silently.",
            "5. Finish your reply with the REUSE REPORT described in the brief "
            "(REUSED: / CREATED: lines) so the user can see what was reused and what was added.",
        ]) + _redaction_note(agent)
        return _result(
            text, mode="host-generates", project=project_path, type=automation_type,
            brief={"system": brief["__system__"], "prompt": brief["__prompt__"]},
            redacted_values=agent.last_redactions,
        )

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
        return _result("\n".join(header) + "\n\nNo files generated." + _redaction_note(agent),
                       mode="no-files", project=project_path, type=automation_type, files=[])
    # Did the generated code reuse what exists? (the model's own report + a static check
    # for calls to methods that exist nowhere). Both are empty/silent when there is nothing
    # to say, so the report text is unchanged in that case.
    reuse_findings = check_calls(result, agent.last_catalog)
    reuse_lines = _reuse_report_lines(agent.last_reuse_report)
    if reuse_findings:
        reuse_lines += _reuse_check_lines(reuse_findings)
    text = ("\n".join(header + context_lines + heal_lines + val_lines + reuse_lines + write_lines
                      + file_blocks)
            + _redaction_note(agent))
    return _result(
        text,
        mode="applied" if write_report is not None else "review-and-apply",
        project=project_path, type=automation_type,
        files=[{"path": p, "content": c} for p, c in result.items()],
        validation=validation, heal_log=heal_log, write_results=write_report,
        reuse_report=agent.last_reuse_report, reuse_check=reuse_findings,
        redacted_values=agent.last_redactions,
    )


# ---------------------------------------------------------------------------
# Validation helper for host-generated code (no model calls)
# ---------------------------------------------------------------------------

@tool_if_enabled(
    "validate_generated_code",
    annotations=ToolAnnotations(
        title="Validate generated code",
        readOnlyHint=True,       # checks only; writes nothing, calls no model
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    ),
)
async def validate_generated_code(
    files: List[FileInput],
    project_path: Optional[str] = None,
    existing_files: Optional[List[FileInput]] = None,
) -> CallToolResult:
    """
    Statically check (syntax/parse) and, where a formatter is installed,
    auto-format files you wrote. Makes NO model calls and writes NOTHING.

    Use after `standalone_automation` returns a brief (host-generates mode):
    pass the files you wrote as {path, content}. Fix any file reported as FAILED
    and call again. Formatted versions are returned only where they changed.

    Optionally pass project_path (same machine) or existing_files [{path, content}]
    to also check that the code only calls methods that exist in the project or in
    your own files — a reuse check (warnings, not failures).
    """
    original = {f.path: f.content for f in files}
    formatted, report = validate_and_format(dict(original))

    lines = ["**Validation:**"]
    for entry in report:
        mark = "✅" if entry.get("ok", True) else "❌ FAILED"
        lines.append(f"- `{entry['file']}` {mark} — {', '.join(entry['checks'])}")
    failed = [e["file"] for e in report if not e.get("ok", True)]
    lines.append("")
    lines.append(f"Fix and re-check: {failed}" if failed else "All files pass static checks.")

    # Optional reuse check against the project's existing code.
    reuse_checked, reuse_findings = False, []
    if existing_files or project_path:
        if not existing_files:
            refusal = _path_not_allowed(project_path)
            if refusal:
                return _result(refusal, mode="refused", project=project_path)
        source = ({f.path: f.content for f in existing_files} if existing_files
                  else load_project_files(project_path) if os.path.isdir(project_path) else {})
        if source:
            reuse_checked = True
            reuse_findings = check_calls(original, build_catalog(source))
        lines += _reuse_check_lines(reuse_findings, reuse_checked)

    changed = [p for p, c in formatted.items() if c != original.get(p)]
    if changed:
        lines += ["", "**Auto-formatted versions (use these):**"]
        for p in changed:
            lines.append(f"### {p}\n```\n{formatted[p]}\n```")
    data = dict(all_ok=not failed, failed=failed, results=report,
                formatted={p: formatted[p] for p in changed})
    if reuse_checked:
        data.update(reuse_ok=not reuse_findings, reuse_check=reuse_findings)
    return _result("\n".join(lines), **data)


# ---------------------------------------------------------------------------
# Prompt — one-step entry point from any MCP client (slash command)
# ---------------------------------------------------------------------------

def _prompt_if_enabled(tool_name: str, **kwargs):
    """Register an MCP prompt only when the tool it drives is enabled."""
    if is_tool_enabled(tool_name):
        return mcp.prompt(**kwargs)
    return lambda fn: fn


@_prompt_if_enabled(
    "standalone_automation",
    name="qeaf_generate",
    title="Generate test automation (QEAF)",
    description="Generate UI/API test automation that matches this project's existing standards.",
)
def qeaf_generate(task: str, project_path: str = "", automation_type: str = "ui") -> str:
    where = (f"The project is at `{project_path}`." if project_path
             else "Use the open workspace as the project.")
    return (
        f"Use the QEAF `standalone_automation` tool to generate {automation_type} test "
        f"automation for the following, matching this project's existing standards and "
        f"reusing its existing methods:\n\n{task}\n\n{where}\n\n"
        "How to proceed:\n"
        "1. If the QEAF server may not be able to read this disk (remote server), first gather "
        "the page objects/helpers, locators, test data, ONE existing test and config, and pass "
        "them as `existing_files`.\n"
        f"2. Call `standalone_automation` with automation_type=\"{automation_type}\". "
        "Do not pass apply=true.\n"
        "3. If it returns a brief (HOST-GENERATES MODE), write the files from it, run "
        "`validate_generated_code` on them, and fix any failures.\n"
        "4. Apply each file through the editor so I can review every diff. Never write silently."
    )


# ---------------------------------------------------------------------------
# Test Analyser — existing tests -> structured test cases (.xlsx)
# ---------------------------------------------------------------------------

_ANALYSE_DESCRIPTION = (
    "Read an EXISTING test project (read-only) and convert each test into structured test "
    "cases — output_format bdd (Given/When/Then), plain, or step_by_step — exported as an "
    ".xlsx file. Pass project_path (same machine) or existing_files [{path, content}]. "
    "Needs a model: the client's (sampling) or a configured key; without one it only returns "
    "the inventory of tests found. The .xlsx is saved outside your project (QEAF_OUTPUT_DIR, "
    "else the system temp folder, or save_to) and its path is returned."
)


def _export_path(save_to: Optional[str], filename: str) -> str:
    if save_to:
        path = os.path.abspath(os.path.expanduser(save_to))
        return path if path.lower().endswith(".xlsx") else os.path.join(path, filename)
    out_dir = os.environ.get("QEAF_OUTPUT_DIR") or os.path.join(tempfile.gettempdir(), "qeaf-exports")
    stem, ext = os.path.splitext(filename)
    return os.path.join(out_dir, f"{stem}_{datetime.now().strftime('%Y%m%d_%H%M%S')}{ext}")


@tool_if_enabled(
    "test_analyser",
    description=_ANALYSE_DESCRIPTION,
    annotations=ToolAnnotations(
        title="Analyse existing tests",
        readOnlyHint=False,      # writes one new .xlsx (never inside the analysed project by default)
        destructiveHint=False,   # timestamped file name; nothing is overwritten
        idempotentHint=False,
        openWorldHint=True,      # may call a model API when a fallback key is configured
    ),
)
async def analyse_tests(
    ctx: Context,
    project_path: Optional[str] = None,
    output_format: str = "bdd",
    language: Optional[str] = None,
    existing_files: Optional[List[FileInput]] = None,
    max_tests: int = 200,
    save_to: Optional[str] = None,
) -> CallToolResult:
    file_map = {f.path: f.content for f in existing_files} if existing_files else None
    logger.info(f"▶ analyse_tests CALLED | format={output_format} max_tests={max_tests} "
                f"remote_files={len(file_map) if file_map else 0}")

    project_path = await _resolve_project_path(ctx, project_path)
    refusal = _path_not_allowed(project_path)
    if not refusal and save_to:
        refusal = _path_not_allowed(os.path.dirname(os.path.abspath(os.path.expanduser(save_to))))
    if refusal:
        logger.warning(f"  └─ {refusal}")
        return _result(refusal, mode="refused", project=project_path)

    if output_format not in SUPPORTED_FORMATS:
        return _result(f"Unsupported output_format '{output_format}'. Use one of: "
                       f"{', '.join(SUPPORTED_FORMATS)}.", mode="error")

    agent = TestAnalyserAgent(_SamplingWithTokenFallbackLLM(ctx),
                              {"language": language, "output_format": output_format})

    # No model available: converting tests needs one, so return what we found instead
    # of silently producing placeholder rows.
    if not _host_can_sample(ctx) and not _fallback_available():
        lang = agent._detect_language(project_path, file_map)
        if file_map:
            tests = agent._discover_from_filemap(file_map, lang)
        elif project_path and os.path.isdir(project_path):
            tests = agent._discover_from_disk(project_path, lang)
        else:
            tests = []
        tests = tests[:max_tests]
        inventory = [{"class": t["class"], "name": t["name"], "file": t["file"], "line": t["line"]}
                     for t in tests]
        lines = [
            "**Test analyser** — INVENTORY ONLY (no model available to convert the tests)",
            f"Language: {lang} | tests found: {len(inventory)}",
            "",
            "Converting tests to BDD/plain/step-by-step needs a model. Use a client that "
            "supports MCP sampling (for example GitHub Copilot in VS Code), or configure a "
            "fallback key (LLM_PROVIDER + its API key). Tests found:",
        ] + [f"- `{t['file']}:{t['line']}` {t['class']}.{t['name']}" for t in inventory[:50]]
        if len(inventory) > 50:
            lines.append(f"- … and {len(inventory) - 50} more")
        return _result("\n".join(lines), mode="inventory-only", language=lang,
                       total_tests=len(inventory), tests=inventory)

    result = await agent.process(project_path=project_path, existing_files=file_map,
                                 max_tests=max_tests)
    if not result.get("excel_b64"):
        return _result(result.get("summary", "No tests found."), mode="no-output",
                       project=project_path, total_scenarios=0)

    path = _export_path(save_to, result["excel_filename"])
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as fh:
        fh.write(base64.b64decode(result["excel_b64"]))
    logger.info(f"  └─ exported {result['total_scenarios']} row(s) → {path}")

    text = "\n".join([
        "**Test analyser** — EXPORTED",
        f"File: {path}",
        f"Format: {output_format} | rows: {result['total_scenarios']}",
        "",
        result["summary"],
    ])
    return _result(text, mode="exported", excel_path=path, format=output_format,
                   total_scenarios=result["total_scenarios"], features=result["features"],
                   summary=result["summary"])


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logger.info(f"Enabled MCP tools: {enabled_tools()}")
    _roots = _allowed_roots()
    logger.info(f"Project allow-list: {_roots if _roots else 'not configured (any folder accepted)'}")
    # stdout is the JSON-RPC channel in stdio mode — human messages go to stderr.
    print(f"Enabled MCP tools: {enabled_tools()}", file=sys.stderr)
    transport = os.environ.get("MCP_TRANSPORT", "stdio")
    if transport == "sse":
        import uvicorn
        host = os.environ.get("MCP_HOST", "0.0.0.0")
        port = int(os.environ.get("MCP_PORT", "8080"))
        print(f"Starting QEAF MCP server at http://{host}:{port}/sse", file=sys.stderr)
        app = mcp.sse_app()
        uvicorn.run(app, host=host, port=port)
    else:
        mcp.run(transport="stdio")
