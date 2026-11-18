import asyncio
import os
import sys

import pytest
from mcp import ClientSession, StdioServerParameters, types
from mcp.client.stdio import stdio_client

from quality_engineering_agentic_framework.agents.automation_agent import AutomationAgent
from quality_engineering_agentic_framework.llm.llm_interface import LLMInterface
from quality_engineering_agentic_framework.utils.reuse_catalog import (
    build_catalog, check_calls, render_catalog, task_keywords, tokens,
)

SERVER = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "mcp_server.py")

MFA_PAGE = """package pages;
public class EngageMfaPage extends BasePage {
    public EngageMfaPage(WebDriver driver) { super(driver); }
    public boolean isContinueWithAccentureButtonPresent() { return true; }
    public void clickContinueWithAccentureButton() { }
    private void internalHelper() { }
}
"""
BASE_PAGE = """package pages;
public class BasePage {
    public WebElement waitForVisibilityOfElement(By locator) { return null; }
}
"""
HOME_PAGE = """package pages;
public class EngageHomePage extends BasePage {
    public boolean isWelcomeTitleDisplayed() { return true; }
    public void clickFindTopTalent() { }
}
"""
TESTS = """package tests;
public class EngageTests {
    @Before public void setup() { }
    @Test public void testLogin() { }
    public void sharedHelper() { }
}
"""
PROJECT = {"pages/EngageMfaPage.java": MFA_PAGE, "pages/BasePage.java": BASE_PAGE,
           "pages/EngageHomePage.java": HOME_PAGE, "tests/EngageTests.java": TESTS}


# ---- catalog ---------------------------------------------------------------

def test_tokens_split_camel_and_snake_case():
    assert tokens("isContinueWithAccentureButtonPresent") >= {"continue", "accenture", "button", "present"}
    assert tokens("click_login_button") == {"click", "login", "button"}
    assert "mfa" in task_keywords("login with MFA page")      # short acronyms count; 'page' is a stopword
    assert "page" not in task_keywords("login with MFA page")


def test_java_catalog_lists_public_methods_but_not_tests_hooks_or_constructors():
    cat = build_catalog(PROJECT)
    assert set(cat.classes["EngageMfaPage"]["methods"]) == {
        "isContinueWithAccentureButtonPresent", "clickContinueWithAccentureButton"}
    assert cat.classes["EngageMfaPage"]["bases"] == ["BasePage"]
    assert set(cat.classes["EngageTests"]["methods"]) == {"sharedHelper"}   # no @Test / @Before


def test_inherited_methods_resolve_through_the_catalog():
    methods, resolved = build_catalog(PROJECT).resolve_methods("EngageMfaPage")
    assert "waitForVisibilityOfElement" in methods and resolved is True


def test_python_js_and_csharp_catalogs():
    py = build_catalog({"pages/login.py": (
        "class LoginPage(BasePage):\n    def open(self, url):\n        pass\n"
        "    def _private(self):\n        pass\n    def test_x(self):\n        pass\n"
        "def helper(a, b):\n    pass\n")})
    assert set(py.classes["LoginPage"]["methods"]) == {"open"}
    assert "helper" in py.functions["pages/login.py"]
    js = build_catalog({"pages/login.js": (
        "export class LoginPage extends Base {\n  async fill(user, pass) {\n  }\n"
        "  click() {\n  }\n}\nexport function wait(ms) {}\n")})
    assert set(js.classes["LoginPage"]["methods"]) == {"fill", "click"}
    assert "wait" in js.functions["pages/login.js"]
    cs = build_catalog({"Pages/Login.cs": (
        "public class LoginPage : BasePage {\n  public void Open(string url) { }\n"
        "  [Test] public void Check() { }\n}\n")})
    assert set(cs.classes["LoginPage"]["methods"]) == {"Open"}


def test_catalog_building_never_raises_on_garbage():
    assert build_catalog({"a.java": "}{ not ((( valid", "b.py": "\x00\x01", "c.txt": "x"}).classes == {}


def test_rendered_catalog_puts_the_most_relevant_class_first_and_respects_the_size_limit():
    cat = build_catalog(PROJECT)
    text = render_catalog(cat, task_keywords("verify the MFA continue button"))
    lines = text.splitlines()
    assert lines[0].lstrip().startswith("EngageMfaPage")
    assert "clickContinueWithAccentureButton" in lines[0]
    assert len(render_catalog(cat, set(), max_chars=120)) < 400


# ---- reuse check -----------------------------------------------------------

def check(code, files=None, path="tests/NewTest.java"):
    return check_calls({path: code}, build_catalog(files or PROJECT))


def test_existing_methods_are_not_flagged():
    assert check("class T { void t() { EngageMfaPage p = new EngageMfaPage(driver); "
                 "p.clickContinueWithAccentureButton(); p.waitForVisibilityOfElement(by); } }") == []


def test_an_invented_method_is_flagged_with_line_and_a_close_suggestion():
    found = check("class T {\n void t() {\n  EngageMfaPage p = new EngageMfaPage(driver);\n"
                  "  p.clickContinueWithAccenture();\n }\n}")
    assert len(found) == 1
    f = found[0]
    assert (f["class"], f["method"], f["line"]) == ("EngageMfaPage", "clickContinueWithAccenture", 4)
    assert "clickContinueWithAccentureButton" in f["suggestions"]


def test_a_method_the_answer_creates_counts_as_existing():
    page = "package pages;\npublic class EngageMfaPage extends BasePage {\n" \
           "  public void clickContinueWithAccenture() { }\n}\n"
    test = "class T { void t() { EngageMfaPage p = new EngageMfaPage(d); p.clickContinueWithAccenture(); } }"
    assert check_calls({"pages/EngageMfaPage.java": page, "tests/T.java": test}, build_catalog(PROJECT)) == []


def test_static_calls_are_checked_too():
    files = {"utils/Driver.java": "public class Driver { public static Object get() { return null; } }"}
    assert check("class T { void t() { Driver.get(); } }", files) == []
    assert [f["method"] for f in check("class T { void t() { Driver.make(); } }", files)] == ["make"]


def test_classes_with_unseen_library_bases_are_never_flagged():
    files = {"pages/P.java": "public class P extends SomeLibraryBase { public void a() { } }"}
    assert check("class T { void t() { P p = new P(); p.inheritedFromLibrary(); } }", files) == []


def test_unknown_classes_and_object_methods_are_ignored():
    assert check("class T { void t() { Foo f = new Foo(); f.bar(); Object o = new Object(); } }") == []
    assert check("class T { void t() { EngageMfaPage p = new EngageMfaPage(d); p.toString(); } }") == []


def test_python_and_js_calls_are_checked():
    py = {"pages/login.py": "class LoginPage:\n    def open(self):\n        pass\n"}
    assert [f["method"] for f in check_calls(
        {"tests/test_a.py": "def test_a():\n    page = LoginPage()\n    page.open()\n    page.submit()\n"},
        build_catalog(py))] == ["submit"]
    js = {"pages/login.js": "export class LoginPage {\n  open() {\n  }\n}\n"}
    assert [f["method"] for f in check_calls(
        {"tests/a.spec.js": "const p = new LoginPage();\np.open();\np.submit();\n"},
        build_catalog(js))] == ["submit"]


def test_no_catalog_means_no_findings():
    assert check_calls({"a.java": "class T {}"}, None) == []


# ---- agent: brief, protocol, report ---------------------------------------

class _Stub(LLMInterface):
    def __init__(self, reply=""):
        self.reply, self.prompts = reply, []

    async def generate(self, prompt, system_message=None, temperature=None, max_tokens=None):
        self.prompts.append(prompt)
        return self.reply

    async def generate_with_json_output(self, *a, **k):
        return {}

    def get_provider_name(self):
        return "stub"


def _brief(task, files):
    agent = AutomationAgent(_Stub(), {"automation_type": "ui"})
    return asyncio.run(agent.process(task, existing_files=files, prepare_only=True))["__prompt__"], agent


def test_brief_has_the_ranked_catalog_and_the_reuse_or_create_protocol():
    prompt, agent = _brief("verify the MFA continue button", PROJECT)
    assert "REUSABLE METHODS" in prompt and "clickContinueWithAccentureButton" in prompt
    assert "REUSE-OR-CREATE PROTOCOL" in prompt and "REUSE FIRST" in prompt and "CREATE ONLY WHEN NOTHING FITS" in prompt
    assert "REUSED: Class.method" in prompt and "CREATED: Class.method (path)" in prompt
    assert agent.last_catalog is not None and "EngageMfaPage" in agent.last_catalog.classes


def test_new_project_gets_no_protocol_because_there_is_nothing_to_reuse():
    prompt, _ = _brief("write login test", {"README.md": "hello"})
    assert "REUSE-OR-CREATE PROTOCOL" not in prompt


def test_camelcase_file_names_now_match_task_words():
    agent = AutomationAgent(_Stub(), {})
    files = {"pages/LoginPage.java": "package pages;\nclass LoginPage { }\n",
             "pages/ZzzOther.java": "package pages;\nclass ZzzOther { }\n"}
    chosen = [p for p, _ in agent._select_relevant_sources(files, "verify login")]
    assert chosen[0] == "pages/LoginPage.java"


def test_reuse_report_is_parsed_outside_code_blocks_only():
    answer = ("```java:A.java\n// REUSED: Fake.inside — must be ignored\nclass A {}\n```\n"
              "REUSE REPORT\nREUSED: EngageMfaPage.clickContinueWithAccentureButton — the click step\n"
              "- CREATED: EngageHomePage.isCategoryDisplayed (pages/EngageHomePage.java) — nothing fit\n")
    report = AutomationAgent._parse_reuse_report(answer)
    assert report["reused"] == ["EngageMfaPage.clickContinueWithAccentureButton — the click step"]
    assert report["created"] == ["EngageHomePage.isCategoryDisplayed (pages/EngageHomePage.java) — nothing fit"]
    assert AutomationAgent._parse_reuse_report("") == {"reused": [], "created": []}


def test_process_records_the_models_report():
    reply = "```java:t.java\nclass T {}\n```\nREUSED: EngageMfaPage.clickContinueWithAccentureButton — click\n"
    agent = AutomationAgent(_Stub(reply), {"automation_type": "ui"})
    asyncio.run(agent.process("mfa", existing_files=PROJECT))
    assert agent.last_reuse_report["reused"] == ["EngageMfaPage.clickContinueWithAccentureButton — click"]


# ---- server paths ------------------------------------------------------------

@pytest.fixture
def project(tmp_path):
    for rel, text in PROJECT.items():
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / rel).write_text(text)
    return str(tmp_path)


INVENTED = ("```java:tests/NewTest.java\npackage tests;\npublic class NewTest {\n"
            "  void t() {\n    EngageMfaPage p = new EngageMfaPage(driver);\n    p.clickContinueWithAccenture();\n  }\n}\n```\n"
            "REUSED: EngageMfaPage.isContinueWithAccentureButtonPresent — presence check\n"
            "CREATED: EngageMfaPage.clickContinueWithAccenture (pages/EngageMfaPage.java) — nothing fit\n")
CLEAN = ("```java:tests/NewTest.java\npackage tests;\npublic class NewTest {\n"
         "  void t() {\n    EngageMfaPage p = new EngageMfaPage(driver);\n    p.clickContinueWithAccentureButton();\n  }\n}\n```\n")


async def _call(tool, args, reply=None, env=None):
    async def sample(ctx, params):
        return types.CreateMessageResult(role="assistant", model="stub", stopReason="endTurn",
                                         content=types.TextContent(type="text", text=reply or ""))

    async def elicit(ctx, params):
        return types.ElicitResult(action="decline")

    kwargs = {"elicitation_callback": elicit}
    if reply is not None:
        kwargs["sampling_callback"] = sample
    params = StdioServerParameters(command=sys.executable, args=[SERVER], env=env or {})
    async with stdio_client(params) as (r, w):
        async with ClientSession(r, w, **kwargs) as session:
            await session.initialize()
            return await session.call_tool(tool, args)


def test_server_shows_the_model_report_and_flags_a_method_that_exists_nowhere(project):
    res = asyncio.run(_call("standalone_automation",
                            {"instructions": "mfa", "project_path": project, "app_url": "https://x.test/"},
                            reply=INVENTED))
    text, data = res.content[0].text, res.structuredContent
    assert "Reuse report (from the model)" in text and "reused EngageMfaPage.isContinue" in text
    assert "Reuse check — calls to methods that don't exist" in text
    assert "clickContinueWithAccenture()" in text and "Similar existing: clickContinueWithAccentureButton" in text
    assert data["reuse_check"][0]["method"] == "clickContinueWithAccenture"
    assert data["reuse_report"]["created"]


def test_server_text_is_unchanged_when_the_code_reuses_correctly_and_gives_no_report(project):
    res = asyncio.run(_call("standalone_automation",
                            {"instructions": "mfa", "project_path": project, "app_url": "https://x.test/"},
                            reply=CLEAN))
    text = res.content[0].text
    assert "Reuse report" not in text and "Reuse check" not in text
    assert res.structuredContent["reuse_check"] == []


def test_validate_tool_runs_the_reuse_check_when_given_project_context(project):
    files = [{"path": "tests/NewTest.java", "content": INVENTED.split("```")[1].split("\n", 1)[1]}]
    res = asyncio.run(_call("validate_generated_code", {"files": files, "project_path": project}))
    assert res.structuredContent["reuse_ok"] is False
    assert res.structuredContent["reuse_check"][0]["method"] == "clickContinueWithAccenture"
    assert "Reuse check" in res.content[0].text
    res = asyncio.run(_call("validate_generated_code", {
        "files": [{"path": "tests/NewTest.java", "content": CLEAN.split("```")[1].split("\n", 1)[1]}],
        "existing_files": [{"path": p, "content": c} for p, c in PROJECT.items()]}))
    assert res.structuredContent["reuse_ok"] is True and "✅" in res.content[0].text


def test_validate_tool_without_project_context_behaves_as_before():
    res = asyncio.run(_call("validate_generated_code",
                            {"files": [{"path": "a.py", "content": "x = 1\n"}]}))
    assert "reuse_ok" not in res.structuredContent and "Reuse check" not in res.content[0].text


def test_validate_tool_respects_the_allow_list(project, tmp_path_factory):
    res = asyncio.run(_call("validate_generated_code",
                            {"files": [{"path": "a.py", "content": "x = 1\n"}], "project_path": project},
                            env={"QEAF_ALLOWED_ROOTS": str(tmp_path_factory.mktemp("elsewhere"))}))
    assert res.structuredContent["mode"] == "refused"
