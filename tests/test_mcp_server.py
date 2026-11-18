import asyncio
import os
import subprocess
import sys

import pytest
from mcp import ClientSession, StdioServerParameters, types
from mcp.client.stdio import stdio_client

import mcp_server
import mcp_tool_flags

SERVER = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "mcp_server.py")
JAVA_TEST = "package tests;\nimport org.junit.Test;\npublic class LoginTest { @Test public void t() {} }\n"


# ---- allow-list (opt-in, off by default) --------------------------------

def test_allowlist_unset_or_empty_means_no_restriction(monkeypatch, tmp_path):
    monkeypatch.delenv("QEAF_ALLOWED_ROOTS", raising=False)
    assert mcp_server._path_not_allowed(str(tmp_path)) is None
    monkeypatch.setenv("QEAF_ALLOWED_ROOTS", "")
    assert mcp_server._path_not_allowed(str(tmp_path)) is None


def test_allowlist_accepts_inside_and_refuses_outside(monkeypatch, tmp_path):
    root, other = tmp_path / "root", tmp_path / "other"
    (root / "sub").mkdir(parents=True)
    other.mkdir()
    monkeypatch.setenv("QEAF_ALLOWED_ROOTS", str(root))
    assert mcp_server._path_not_allowed(str(root)) is None
    assert mcp_server._path_not_allowed(str(root / "sub")) is None
    assert "Refused" in mcp_server._path_not_allowed(str(other))


def test_allowlist_blocks_dotdot_and_symlink_escapes(monkeypatch, tmp_path):
    root, outside = tmp_path / "root", tmp_path / "outside"
    root.mkdir()
    outside.mkdir()
    os.symlink(outside, root / "link")
    monkeypatch.setenv("QEAF_ALLOWED_ROOTS", str(root))
    assert mcp_server._path_not_allowed(str(root / ".." / "outside")) is not None
    assert mcp_server._path_not_allowed(str(root / "link")) is not None


def test_allowlist_supports_several_roots(monkeypatch, tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    a.mkdir()
    b.mkdir()
    monkeypatch.setenv("QEAF_ALLOWED_ROOTS", os.pathsep.join([str(a), str(b)]))
    assert mcp_server._path_not_allowed(str(b)) is None


def test_allowlist_ignores_missing_project_path(monkeypatch, tmp_path):
    monkeypatch.setenv("QEAF_ALLOWED_ROOTS", str(tmp_path))
    assert mcp_server._path_not_allowed(None) is None


# ---- fallback detection / flags -----------------------------------------

@pytest.mark.parametrize("provider,var", [("copilot", "GITHUB_TOKEN"), ("openai", "OPENAI_API_KEY"),
                                          ("gemini", "GEMINI_API_KEY")])
def test_fallback_available_depends_on_the_providers_key(monkeypatch, provider, var):
    for v in ("GITHUB_TOKEN", "OPENAI_API_KEY", "GEMINI_API_KEY"):
        monkeypatch.delenv(v, raising=False)
    monkeypatch.setenv("LLM_PROVIDER", provider)
    assert mcp_server._fallback_available() is False
    monkeypatch.setenv(var, "x")
    assert mcp_server._fallback_available() is True


def test_flags_default_env_override_and_unknown(monkeypatch):
    monkeypatch.delenv("QEAF_ENABLE_STANDALONE_AUTOMATION", raising=False)
    assert mcp_tool_flags.is_tool_enabled("standalone_automation") is True
    monkeypatch.setenv("QEAF_ENABLE_STANDALONE_AUTOMATION", "off")
    assert mcp_tool_flags.is_tool_enabled("standalone_automation") is False
    assert mcp_tool_flags.is_tool_enabled("no_such_tool") is False


# ---- tool registration: annotations and description size ----------------

def test_tools_are_registered_with_annotations_and_a_short_description():
    tools = {t.name: t for t in asyncio.run(mcp_server.mcp.list_tools())}
    assert {"standalone_automation", "validate_generated_code"} <= set(tools)
    main, check = tools["standalone_automation"], tools["validate_generated_code"]
    assert len(main.description) < 1800          # was ~4.5k characters
    assert main.annotations.destructiveHint is True and main.annotations.readOnlyHint is False
    assert check.annotations.readOnlyHint is True and check.annotations.idempotentHint is True


def test_validate_tool_reports_failures():
    res = asyncio.run(mcp_server.validate_generated_code([
        mcp_server.FileInput(path="ok.py", content="x = 1\n"),
        mcp_server.FileInput(path="bad.py", content="def f(:\n")]))
    out = res.content[0].text
    assert "bad.py" in out and "FAILED" in out and "ok.py" in out
    assert res.structuredContent["all_ok"] is False
    assert res.structuredContent["failed"] == ["bad.py"]


# ---- stdio protocol ------------------------------------------------------

def test_stdout_is_clean_in_stdio_mode():
    proc = subprocess.run([sys.executable, "-u", SERVER], input="", capture_output=True,
                          text=True, timeout=90)
    assert proc.stdout == ""      # stdout is the JSON-RPC channel; messages go to stderr
    assert "Enabled MCP tools" in proc.stderr


async def _call(project, env, with_sampling):
    async def sampling(ctx, params):
        return types.CreateMessageResult(
            role="assistant", model="stub", stopReason="endTurn",
            content=types.TextContent(type="text",
                                      text="```java:tests/Gen.java\nclass Gen {}\n```"))

    async def elicit(ctx, params):
        return types.ElicitResult(action="decline")

    kwargs = {"elicitation_callback": elicit}
    if with_sampling:
        kwargs["sampling_callback"] = sampling
    params = StdioServerParameters(command=sys.executable, args=[SERVER], env=env)
    async with stdio_client(params) as (r, w):
        async with ClientSession(r, w, **kwargs) as session:
            await session.initialize()
            res = await session.call_tool("standalone_automation", {
                "instructions": "login test", "project_path": project, "app_url": "https://x.test/"})
            return res.content[0].text


@pytest.fixture
def java_project(tmp_path):
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "LoginTest.java").write_text(JAVA_TEST)
    return str(tmp_path)


def test_host_without_sampling_or_key_gets_the_brief(java_project):
    text = asyncio.run(_call(java_project, {}, with_sampling=False))
    assert "HOST-GENERATES MODE" in text and "error.txt" not in text
    assert "LoginTest" in text                       # real project source is in the brief


def test_sampling_host_still_gets_server_generated_files(java_project):
    text = asyncio.run(_call(java_project, {}, with_sampling=True))
    assert "REVIEW & APPLY" in text and "HOST-GENERATES" not in text
    assert "tests/Gen.java" in text


def test_allowlist_refuses_over_the_wire(java_project, tmp_path_factory):
    elsewhere = str(tmp_path_factory.mktemp("elsewhere"))
    text = asyncio.run(_call(java_project, {"QEAF_ALLOWED_ROOTS": elsewhere}, with_sampling=True))
    assert text.startswith("Refused")
