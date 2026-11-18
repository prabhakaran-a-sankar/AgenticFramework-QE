import asyncio
import os
import sys

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from quality_engineering_agentic_framework.agents.automation_agent import AutomationAgent
from quality_engineering_agentic_framework.llm.llm_interface import LLMInterface
from quality_engineering_agentic_framework.utils.code_validation import validate_and_format
from quality_engineering_agentic_framework.utils.reuse_catalog import (
    build_catalog, check_calls, parse_feature, render_catalog, render_steps, step_regex,
)

SERVER = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "mcp_server.py")

# ---------------------------------------------------------------- fixtures --

PW_FIXTURES = """import { test as base } from '@playwright/test';
import { LoginPage } from '../pages/LoginPage';
export const test = base.extend<{ loginPage: LoginPage; plain: string }>({
  loginPage: async ({ page }, use) => {
    await use(new LoginPage(page));
  },
  plain: async ({}, use) => { await use('x'); },
});
"""
PW_PAGE = "export class LoginPage {\n  async goto() {\n  }\n  async login(u, p) {\n  }\n}\n"
PW_FILES = {"fixtures/index.ts": PW_FIXTURES, "pages/LoginPage.ts": PW_PAGE}

PY_CONFTEST = ("import pytest\nfrom pages.login_page import LoginPage\n\n"
               "@pytest.fixture\ndef login_page(page):\n    return LoginPage(page)\n\n"
               "@pytest.fixture\ndef raw():\n    return 1\n")
PY_PAGE = "class LoginPage:\n    def open(self):\n        pass\n"
PY_FILES = {"conftest.py": PY_CONFTEST, "pages/login_page.py": PY_PAGE}


def test_playwright_fixtures_are_catalogued_with_their_classes():
    fx = build_catalog(PW_FILES).fixtures
    assert fx["loginPage"] == {"file": "fixtures/index.ts", "class": "LoginPage"}
    assert fx["plain"]["class"] is None                      # a fixture that isn't a page object


def test_pytest_fixtures_are_catalogued_but_not_listed_as_callable_methods():
    cat = build_catalog(PY_FILES)
    assert cat.fixtures["login_page"]["class"] == "LoginPage" and cat.fixtures["raw"]["class"] is None
    assert "login_page" not in cat.functions.get("conftest.py", {})


def test_unrelated_extend_calls_are_not_fixtures():
    assert build_catalog({"a.js": "_.extend(target, { a: 1 });\nconst x = foo.extend({});"}).fixtures == {}


def test_rendered_catalog_lists_fixtures_first():
    text = render_catalog(build_catalog(PW_FILES), set())
    assert text.splitlines()[0].lstrip().startswith("FIXTURES")
    assert "loginPage → LoginPage" in text


def test_invented_method_on_an_injected_playwright_fixture_is_flagged():
    spec = ("import { test } from '../fixtures';\n"
            "test('x', async ({ page, loginPage }) => {\n  await loginPage.goto();\n"
            "  await loginPage.signIn();\n});\n")
    found = check_calls({"tests/a.spec.ts": spec}, build_catalog(PW_FILES))
    assert [(f["class"], f["method"]) for f in found] == [("LoginPage", "signIn")]


def test_existing_methods_on_fixtures_are_not_flagged_and_builtin_fixtures_are_ignored():
    spec = "test('x', async ({ page, request, loginPage }) => {\n  await loginPage.login('a','b');\n});\n"
    assert check_calls({"tests/a.spec.ts": spec}, build_catalog(PW_FILES)) == []


def test_invented_method_on_a_pytest_fixture_is_flagged():
    test = "def test_x(login_page, page):\n    login_page.open()\n    login_page.sign_in()\n"
    found = check_calls({"tests/test_a.py": test}, build_catalog(PY_FILES))
    assert [(f["class"], f["method"]) for f in found] == [("LoginPage", "sign_in")]


def test_a_fixture_added_in_the_answer_counts():
    new_fixture = ("import { test as base } from '@playwright/test';\n"
                   "export const test = base.extend({\n  loginPage: async ({ page }, use) => {\n"
                   "    await use(new LoginPage(page));\n  },\n});\n")
    spec = "test('x', async ({ loginPage }) => {\n  await loginPage.goto();\n  await loginPage.nope();\n});\n"
    found = check_calls({"fixtures/new.ts": new_fixture, "tests/a.spec.ts": spec},
                        build_catalog({"pages/LoginPage.ts": PW_PAGE}))
    assert [f["method"] for f in found] == ["nope"]


# ----------------------------------------------------------------- gherkin --

STEPS_JAVA = r'''package steps;
public class LoginSteps {
    @Given("I am on the login page")
    public void iAmOnTheLoginPage() { }
    @When("I enter {string} and {string}")
    public void iEnter(String u, String p) { }
    @Then("^I should see the (\\w+) dashboard$")
    public void iShouldSeeDashboard(String name) { }
    @And("I click the continue button")
    public void iClick() { }
}
'''
FEATURE = '''@smoke @login
Feature: Login
  As a user
  I want to sign in
  So that I can see my dashboard

  Background:
    Given I am on the login page

  Scenario: Successful login
    When I enter "alice" and "secret"
    Then I should see the admin dashboard

  Scenario Outline: Several users
    When I enter "<user>" and "<pw>"
    And I click the continue button
    Then I should see the <role> dashboard

    Examples:
      | user  | pw     | role  |
      | alice | secret | admin |
'''
GH_FILES = {"src/test/java/steps/LoginSteps.java": STEPS_JAVA, "src/test/resources/features/login.feature": FEATURE}


def test_step_definitions_are_extracted_for_each_host_language():
    java = build_catalog({"S.java": STEPS_JAVA}).steps
    assert [s["pattern"] for s in java] == [
        "I am on the login page", "I enter {string} and {string}",
        r"^I should see the (\w+) dashboard$", "I click the continue button"]
    js = build_catalog({"steps/s.js": ("const { Given, When } = require('@cucumber/cucumber');\n"
                                       "Given('I am logged in', async function () {});\n"
                                       "When(/^I add (\\d+) items$/, async function (n) {});\n")}).steps
    assert [(s["pattern"], s["regex"]) for s in js] == [("I am logged in", False), (r"^I add (\d+) items$", True)]
    py = build_catalog({"features/steps/s.py": ("@given('I have a cart')\ndef a(c): pass\n"
                                                "@when(u'I add {n:d} items')\ndef b(c, n): pass\n")}).steps
    assert [s["pattern"] for s in py] == ["I have a cart", "I add {n:d} items"]
    cs = build_catalog({"Steps.cs": '[Given(@"I open ""home""")]\npublic void A() {}\n[When("I wait")]\npublic void B() {}\n'}).steps
    assert [s["pattern"] for s in cs] == ['I open "home"', "I wait"]


@pytest.mark.parametrize("pattern,text,expected", [
    ("I enter {string} and {string}", 'I enter "a" and "b"', True),
    ("I enter {string} and {string}", "I enter a and b", False),
    ("I have {int} items", "I have 12 items", True),
    ("I have {int} items", "I have many items", False),
    ("I have {int} cucumber(s)", "I have 3 cucumbers", True),
    ("I click/press the button", "I press the button", True),
    ("I add {n:d} items", "I add 4 items", True),                      # behave / parse style
    (r"^I should see the (\w+) dashboard$", "I should see the admin dashboard", True),
    (r"^I should see the (\w+) dashboard$", "I should see the admin page", False),
    ("I am on the login page", "I am on the login page", True),
    ("I am on the login page", "I am on the login page now", False),
])
def test_step_phrases_match_cucumber_expressions_regexes_and_parse_style(pattern, text, expected):
    assert bool(step_regex(pattern).match(text)) is expected


def test_feature_files_are_parsed():
    parsed = parse_feature(FEATURE)
    assert parsed["feature"] == "Login"
    assert parsed["scenarios"] == ["Successful login", "Several users"]
    assert [s["text"] for s in parsed["steps"]][:2] == ["I am on the login page", 'I enter "alice" and "secret"']
    assert all(s["line"] > 0 for s in parsed["steps"])


def test_generated_scenarios_that_use_existing_steps_are_not_flagged():
    assert check_calls({"features/new.feature": FEATURE}, build_catalog(GH_FILES)) == []


def test_an_undefined_step_is_flagged_with_the_closest_existing_phrase():
    feature = ("Feature: X\n  Scenario: Y\n    Given I am on the login page\n"
               "    When I click the continue buton\n")
    found = check_calls({"features/x.feature": feature}, build_catalog(GH_FILES))
    assert len(found) == 1 and found[0]["kind"] == "step" and found[0]["line"] == 4
    assert "I click the continue button" in found[0]["suggestions"]


def test_a_step_definition_added_in_the_answer_makes_the_phrase_defined():
    feature = "Feature: X\n  Scenario: Y\n    Given I am on the login page\n    When I accept the cookies\n"
    new_def = "package steps;\npublic class CookieSteps {\n  @When(\"I accept the cookies\")\n  public void a() { }\n}\n"
    assert check_calls({"features/x.feature": feature, "steps/CookieSteps.java": new_def},
                       build_catalog(GH_FILES)) == []


def test_no_check_when_no_step_definitions_are_visible():
    feature = "Feature: X\n  Scenario: Y\n    Given anything at all\n"
    assert check_calls({"features/x.feature": feature}, build_catalog({"features/old.feature": FEATURE})) == []


def test_rendered_steps_put_task_relevant_phrases_first_and_fall_back_to_feature_steps():
    text = render_steps(build_catalog(GH_FILES), {"continue", "button"})
    assert text.splitlines()[0].strip().startswith("And I click the continue button")
    only_features = render_steps(build_catalog({"f.feature": FEATURE}), set())
    assert "I am on the login page" in only_features


# --------------------------------------------------------- gherkin validator --

def gherkin_ok(code):
    return validate_and_format({"x.feature": code})[1][0]["ok"]


def test_valid_feature_passes_and_descriptions_and_docstrings_are_not_errors():
    assert gherkin_ok(FEATURE)
    assert gherkin_ok('Feature: F\n  free text description\n  Scenario: S\n    Given a doc\n      """\n'
                      '      | not a table\n      """\n')


def test_structural_problems_are_hard_failures():
    assert not gherkin_ok("Scenario: no feature line\n  Given x\n")
    assert not gherkin_ok("Feature: F\n  Scenario Outline: S\n    Given <a>\n")          # no Examples
    assert not gherkin_ok("Feature: F\n  Scenario Outline: S\n    Given <a>\n    Examples:\n"
                          "      | a | b |\n      | 1 |\n")                              # ragged table


# ------------------------------------------------------------ agent behaviour --

class _Stub(LLMInterface):
    def __init__(self):
        self.prompts = []

    async def generate(self, prompt, system_message=None, temperature=None, max_tokens=None):
        self.prompts.append(prompt)
        return ""

    async def generate_with_json_output(self, *a, **k):
        return {}

    def get_provider_name(self):
        return "stub"


def _brief(task, **kw):
    agent = AutomationAgent(_Stub(), {"automation_type": "ui"})
    return asyncio.run(agent.process(task, prepare_only=True, **kw))["__prompt__"], agent


@pytest.fixture
def gherkin_project(tmp_path):
    files = dict(GH_FILES)
    files["pom.xml"] = "<project>cucumber selenium</project>"
    files["src/test/java/pages/LoginPage.java"] = "package pages;\npublic class LoginPage { public void open() { } }\n"
    for rel, text in files.items():
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / rel).write_text(text)
    return str(tmp_path)


def test_gherkin_project_brief_has_steps_protocol_and_a_feature_as_the_example(gherkin_project):
    prompt, agent = _brief("login with admin", project_path=gherkin_project)
    assert "REUSABLE STEPS" in prompt and "I click the continue button" in prompt
    assert "GHERKIN / BDD PROTOCOL" in prompt and "REUSE EXISTING STEPS" in prompt
    example = prompt.split("EXAMPLE EXISTING TEST")[1].split("---")[1]
    assert example.strip().endswith("login.feature")
    assert "features" in prompt.split("EXISTING DIRECTORY LAYOUT")[1].split("RELEVANT")[0]
    contract = prompt.split("derived from the example):")[1].split("REUSABLE")[0]
    assert "Scenario Outline" in contract and "Background" in contract and "@smoke" in contract
    assert 'first person' in contract and "double quotes" in contract


def test_gherkin_signatures_are_not_polluted_by_feature_text(gherkin_project):
    agent = AutomationAgent(_Stub(), {})
    profile = agent._scan_framework(gherkin_project, "java")
    assert "login.feature" in " ".join(profile["sources"])
    assert "login.feature" not in profile["existing_code"]


def test_projects_without_feature_files_are_unaffected():
    files = {"pom.xml": "<project/>", "pages/LoginPage.java": "package pages;\npublic class LoginPage { public void open() { } }\n",
             "tests/LoginTest.java": "package tests;\nimport org.junit.Test;\npublic class LoginTest { @Test public void t() { } }\n"}
    prompt, _ = _brief("login", existing_files=files)
    assert "REUSABLE STEPS" not in prompt and "GHERKIN / BDD PROTOCOL" not in prompt


def test_feature_files_alone_do_not_switch_gherkin_mode_on():
    prompt, _ = _brief("login", existing_files={"features/login.feature": FEATURE,
                                                 "tests/LoginTest.java": "package tests;\npublic class LoginTest { }\n"})
    assert "GHERKIN / BDD PROTOCOL" not in prompt          # needs step definitions too


# ----------------------------------------------------------------- server ----

def test_validate_tool_checks_generated_feature_files_against_existing_steps():
    async def run():
        params = StdioServerParameters(command=sys.executable, args=[SERVER], env={})
        feature = "Feature: X\n  Scenario: Y\n    Given I am on the login page\n    When I do something new\n"
        async with stdio_client(params) as (r, w):
            async with ClientSession(r, w) as s:
                await s.initialize()
                return await s.call_tool("validate_generated_code", {
                    "files": [{"path": "features/x.feature", "content": feature}],
                    "existing_files": [{"path": p, "content": c} for p, c in GH_FILES.items()]})
    res = asyncio.run(run())
    data = res.structuredContent
    assert data["all_ok"] is True and data["reuse_ok"] is False
    assert data["reuse_check"][0]["kind"] == "step" and "I do something new" in data["reuse_check"][0]["step"]
    assert "matches no existing step" in res.content[0].text
