"""Structured output, MCP prompt, and the Test Analyser tool (over the real stdio protocol)."""
import asyncio
import json
import os
import sys

import pytest
from mcp import ClientSession, StdioServerParameters, types
from mcp.client.stdio import stdio_client

import mcp_server
from quality_engineering_agentic_framework.agents.test_analyser_agent import (
    TestAnalyserAgent as _Analyser,   # alias: pytest would otherwise try to collect "Test*"
)

SERVER = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "mcp_server.py")

JAVA_TEST = ("package tests;\nimport org.junit.Test;\npublic class LoginTest {\n"
             "  @Test\n  public void loginWorks() { }\n  @Test\n  public void loginShown() { }\n}\n")


@pytest.fixture
def java_project(tmp_path):
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "LoginTest.java").write_text(JAVA_TEST)   # note: no pom.xml
    return str(tmp_path)


ANALYSER_ROWS = json.dumps([
    {"index": 0, "feature": "Login", "scenario": "Works", "given": ["a user"], "when": ["logs in"],
     "then": ["sees home"], "tags": ["@smoke"]},
    {"index": 1, "feature": "Login", "scenario": "Shown", "given": ["a user"], "when": ["opens"],
     "then": ["sees page"], "tags": []}])


async def _session_call(tool, args, env=None, sampling=True):
    async def sample(ctx, params):
        text = ANALYSER_ROWS if tool == "analyse_tests" else "```java:tests/Gen.java\nclass Gen {}\n```"
        return types.CreateMessageResult(role="assistant", model="stub", stopReason="endTurn",
                                         content=types.TextContent(type="text", text=text))

    async def elicit(ctx, params):
        return types.ElicitResult(action="decline")

    kwargs = {"elicitation_callback": elicit}
    if sampling:
        kwargs["sampling_callback"] = sample
    params = StdioServerParameters(command=sys.executable, args=[SERVER], env=env or {})
    async with stdio_client(params) as (r, w):
        async with ClientSession(r, w, **kwargs) as session:
            await session.initialize()
            return await session.call_tool(tool, args)


# ---- structured output ---------------------------------------------------

def test_brief_mode_returns_text_and_structured_data(java_project):
    res = asyncio.run(_session_call("standalone_automation", {
        "instructions": "login test", "project_path": java_project, "app_url": "https://x.test/"},
        sampling=False))
    assert "HOST-GENERATES MODE" in res.content[0].text
    data = res.structuredContent
    assert data["mode"] == "host-generates"
    assert "LoginTest" in data["brief"]["prompt"] and data["redacted_values"] == 0


def test_server_generated_result_has_files_and_validation(java_project):
    res = asyncio.run(_session_call("standalone_automation", {
        "instructions": "login test", "project_path": java_project, "app_url": "https://x.test/"}))
    assert "REVIEW & APPLY" in res.content[0].text          # text report unchanged
    data = res.structuredContent
    assert data["result"] == res.content[0].text            # backward-compatible key kept
    assert data["mode"] == "review-and-apply"
    assert data["files"] == [{"path": "tests/Gen.java", "content": "class Gen {}"}]
    assert data["validation"][0]["file"] == "tests/Gen.java"


def test_refusal_is_structured_too(java_project, tmp_path_factory):
    res = asyncio.run(_session_call(
        "standalone_automation",
        {"instructions": "x", "project_path": java_project},
        env={"QEAF_ALLOWED_ROOTS": str(tmp_path_factory.mktemp("elsewhere"))}))
    assert res.content[0].text.startswith("Refused") and res.structuredContent["mode"] == "refused"


# ---- MCP prompt -----------------------------------------------------------

def test_prompt_is_registered_and_renders_the_task():
    prompts = {p.name for p in asyncio.run(mcp_server.mcp.list_prompts())}
    assert "qeaf_generate" in prompts
    rendered = asyncio.run(mcp_server.mcp.get_prompt(
        "qeaf_generate", {"task": "login with MFA", "project_path": "/p", "automation_type": "api"}))
    text = rendered.messages[0].content.text
    assert "login with MFA" in text and "`/p`" in text and "automation_type=\"api\"" in text
    assert "Do not pass apply=true" in text


# ---- Test Analyser tool ----------------------------------------------------

def test_analyse_tool_is_registered_with_annotations():
    tools = {t.name: t for t in asyncio.run(mcp_server.mcp.list_tools())}
    tool = tools["analyse_tests"]
    assert tool.annotations.destructiveHint is False and len(tool.description) < 1000


def test_analyser_detects_language_without_a_marker_file(java_project):
    assert _Analyser(None, {})._detect_language(java_project, None) == "java"


def test_analyse_exports_an_xlsx_outside_the_project(java_project, tmp_path_factory):
    out_dir = str(tmp_path_factory.mktemp("exports"))
    res = asyncio.run(_session_call("analyse_tests", {"project_path": java_project},
                                    env={"QEAF_OUTPUT_DIR": out_dir}))
    data = res.structuredContent
    assert data["mode"] == "exported" and data["total_scenarios"] == 2
    assert data["excel_path"].startswith(out_dir) and not data["excel_path"].startswith(java_project)
    with open(data["excel_path"], "rb") as fh:
        assert fh.read(2) == b"PK"                      # a real .xlsx (zip) file
    assert "EXPORTED" in res.content[0].text


def test_analyse_without_a_model_returns_the_inventory_only(java_project):
    res = asyncio.run(_session_call("analyse_tests", {"project_path": java_project}, sampling=False))
    data = res.structuredContent
    assert data["mode"] == "inventory-only" and data["total_tests"] == 2
    assert "INVENTORY ONLY" in res.content[0].text


def test_analyse_rejects_unknown_format_and_respects_allowlist(java_project, tmp_path_factory):
    res = asyncio.run(_session_call("analyse_tests", {"project_path": java_project,
                                                      "output_format": "pdf"}))
    assert res.structuredContent["mode"] == "error"
    res = asyncio.run(_session_call(
        "analyse_tests", {"project_path": java_project},
        env={"QEAF_ALLOWED_ROOTS": str(tmp_path_factory.mktemp("elsewhere"))}))
    assert res.structuredContent["mode"] == "refused"
