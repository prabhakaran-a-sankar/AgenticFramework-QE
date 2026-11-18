import asyncio
import os

from quality_engineering_agentic_framework.agents.automation_agent import AutomationAgent
from quality_engineering_agentic_framework.llm.llm_interface import LLMInterface

JAVA_PAGE = "package pages;\npublic class LoginPage { public void clickLogin() {} }\n"
JAVA_TEST = ("package tests;\nimport org.junit.Test;\n"
             "public class LoginTest { @Test public void t() {} }\n")


class StubLLM(LLMInterface):
    """Records prompts and returns a canned single-file answer."""

    def __init__(self):
        self.prompts = []

    async def generate(self, prompt, system_message=None, temperature=None, max_tokens=None):
        self.prompts.append(prompt)
        return "```java:tests/Gen.java\nclass Gen {}\n```"

    async def generate_with_json_output(self, *a, **k):
        return {}

    def get_provider_name(self):
        return "stub"


def make_project(tmp_path, files):
    for rel, content in files.items():
        path = tmp_path / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
    return str(tmp_path)


def run(agent_cfg=None, **kwargs):
    llm = StubLLM()
    agent = AutomationAgent(llm, agent_cfg or {})
    result = asyncio.run(agent.process("write a login test", **kwargs))
    return llm, result


# ---- language detection -------------------------------------------------

def test_language_is_inferred_from_sources_when_no_marker_file(tmp_path):
    project = make_project(tmp_path, {"pages/LoginPage.java": JAVA_PAGE,
                                      "tests/LoginTest.java": JAVA_TEST})
    llm, _ = run(project_path=project)
    assert "Detected language: java" in llm.prompts[0]
    assert "EXTEND the existing project" in llm.prompts[0]


def test_marker_file_wins_over_extension_counts(tmp_path):
    project = make_project(tmp_path, {"pom.xml": "<project/>", "a.py": "x=1", "b.py": "y=2",
                                      "c.py": "z=3", "tests/LoginTest.java": JAVA_TEST})
    llm, _ = run(project_path=project)
    assert "Detected language: java" in llm.prompts[0]


def test_explicit_language_wins(tmp_path):
    project = make_project(tmp_path, {"a.py": "x=1", "b.py": "y=2"})
    llm, _ = run({"language": "java"}, project_path=project)
    assert "Detected language: java" in llm.prompts[0]


def test_empty_project_defaults_to_new_python_project(tmp_path):
    project = make_project(tmp_path, {"README.md": "hello"})
    llm, _ = run(project_path=project)
    assert "Detected language: python" in llm.prompts[0]
    assert "NEW project foundation" in llm.prompts[0]


def test_agent_fed_files_path_is_unchanged():
    llm, _ = run(existing_files={"tests/LoginTest.java": JAVA_TEST,
                                 "pages/LoginPage.java": JAVA_PAGE})
    assert "Detected language: java" in llm.prompts[0]
    assert "EXTEND the existing project" in llm.prompts[0]


# ---- prepare_only (host-generates) -------------------------------------

def test_prepare_only_returns_brief_and_makes_no_model_call(tmp_path):
    project = make_project(tmp_path, {"pages/LoginPage.java": JAVA_PAGE,
                                      "tests/LoginTest.java": JAVA_TEST})
    llm, result = run(project_path=project, prepare_only=True)
    assert llm.prompts == []
    assert set(result) == {"__prompt__", "__system__"}
    assert "LoginPage" in result["__prompt__"]          # real source is in the brief
    assert "NEVER invent methods" in result["__system__"]


# ---- helpers ------------------------------------------------------------

def test_parse_files_from_response():
    agent = AutomationAgent(StubLLM(), {})
    out = agent._parse_files_from_response(
        "```java:tests/A.java\nclass A {}\n```\ntext\n```python:b.py\nx = 1\n```")
    assert out == {"tests/A.java": "class A {}", "b.py": "x = 1"}


def test_write_files_refuses_paths_that_escape_the_project(tmp_path):
    project = tmp_path / "proj"
    project.mkdir()
    report = AutomationAgent.write_files({"../evil.txt": "x"}, str(project))
    assert report[0]["status"] == "refused"
    assert not (tmp_path / "evil.txt").exists()


def test_write_files_creates_then_updates(tmp_path):
    first = AutomationAgent.write_files({"tests/A.java": "v1"}, str(tmp_path))
    second = AutomationAgent.write_files({"tests/A.java": "v2"}, str(tmp_path))
    assert first[0]["status"] == "created" and second[0]["status"] == "updated"
    assert (tmp_path / "tests" / "A.java").read_text() == "v2"


def test_discover_config_finds_base_url_and_auth():
    found = AutomationAgent.discover_config(
        files={".env": "BASE_URL=https://app.test/\nAuthorization: Bearer abc"})
    assert found["base_url"] == "https://app.test"
    assert found["auth"] == "bearer"


def test_discover_config_returns_empty_when_nothing_found():
    assert AutomationAgent.discover_config(files={"README.md": "nothing here"}) == {
        "base_url": "", "auth": ""}
