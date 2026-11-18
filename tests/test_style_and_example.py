import asyncio

from quality_engineering_agentic_framework.agents.automation_agent import AutomationAgent as A
from quality_engineering_agentic_framework.llm.llm_interface import LLMInterface

PLAYWRIGHT_SPEC = (
    "import { test, expect } from '@playwright/test';\n"
    "import { username, loginButton } from '../pages/loginPage.js';\n"
    "import { testData } from '../data/testData.js';\n"
    "test.describe('login', () => {\n"
    "  test('standard user logs in', async ({ page }) => {\n"
    "    await page.goto('/');\n"
    "    await page.fill(username, testData.standard_user);\n"
    "    await page.click(loginButton);\n"
    "  });\n});\n")

JUNIT4 = ("package tests;\nimport org.junit.*;\nimport org.openqa.selenium.chrome.ChromeDriver;\n"
          "import pages.EngageMfaPage;\npublic class EngageTests {\n  WebDriver driver;\n"
          "  @Before public void setup() { driver = new ChromeDriver(); }\n"
          "  @Test public void testMfaPage() {\n    EngageMfaPage p = new EngageMfaPage(driver);\n"
          "    Assert.assertTrue(p.isShown());\n  }\n"
          "  @After public void teardown() { driver.quit(); }\n}\n")


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


def brief(files, task):
    agent = A(_Stub(), {"automation_type": "ui"})
    return asyncio.run(agent.process(task, existing_files=files, prepare_only=True))["__prompt__"]


# ---- the example is chosen first -----------------------------------------

def test_js_style_rules_are_unchanged():
    notes = A._analyze_test_style(PLAYWRIGHT_SPEC)
    assert len(notes) == 5
    assert A._analyze_test_style(PLAYWRIGHT_SPEC, "javascript") == notes   # nothing extra for JS


def test_example_keeps_its_style_rules_when_the_task_name_matches_the_test_file():
    files = {"package.json": '{"devDependencies":{"@playwright/test":"1"}}',
             "pages/loginPage.js": "export const username = '#u';\n",
             "tests/login.spec.js": PLAYWRIGHT_SPEC}
    prompt = brief(files, "login test")                   # task words match the file name
    assert "STYLE CONTRACT — your generated test MUST follow" in prompt
    assert "EXAMPLE EXISTING TEST" in prompt
    assert prompt.count("--- tests/login.spec.js ---") == 1   # shown once, not twice


def test_relevant_sources_never_repeat_the_example():
    files = {"tests/login.spec.js": PLAYWRIGHT_SPEC, "pages/loginPage.js": "export const a = 1;\n"}
    agent = A(_Stub(), {})
    example = A._pick_example_test(files, set(), A._task_keywords("login test"))
    relevant = agent._select_relevant_sources(files, "login test", exclude={example[0]})
    assert example[0] not in [p for p, _ in relevant]


def test_example_prefers_the_test_that_matches_the_task():
    files = {"tests/a_login.spec.js": "test('a')", "tests/checkout.spec.js": "test('b')"}
    assert A._pick_example_test(files, set(), {"checkout", "totals"})[0] == "tests/checkout.spec.js"


def test_example_falls_back_to_the_first_test_file_without_a_match():
    files = {"tests/a_login.spec.js": "test('a')", "tests/checkout.spec.js": "test('b')"}
    assert A._pick_example_test(files, set())[0] == "tests/a_login.spec.js"
    assert A._pick_example_test(files, set(), {"unrelated"})[0] == "tests/a_login.spec.js"
    assert A._pick_example_test(files, {"tests/a_login.spec.js"})[0] == "tests/checkout.spec.js"


def test_generic_words_do_not_drive_the_example_choice():
    files = {"tests/first.spec.js": "test('a')", "tests/second.spec.js": "test('b')"}
    # "test" / "write" are in every name or task and must not decide anything
    assert A._pick_example_test(files, set(), {"write", "test", "generate"})[0] == "tests/first.spec.js"


def test_no_test_files_means_no_example():
    assert A._pick_example_test({"pages/LoginPage.java": "class X {}"}, set()) is None


# ---- Java / Python / C# style rules ---------------------------------------

def joined(language, code):
    return "\n".join(A._analyze_test_style(code, language))


def test_java_junit4_rules_follow_the_example():
    rules = joined("java", JUNIT4)
    assert "JUnit 4" in rules and "do not mix in JUnit 5 or TestNG" in rules
    assert "Assert.assertXxx" in rules
    assert "WebDriver inline" in rules
    assert "new <Name>Page(driver)" in rules and "EngageMfaPage" in rules
    assert "driver.quit()" in rules
    assert "`testMfaPage`" in rules


def test_java_junit5_and_testng_are_told_apart():
    assert "JUnit 5" in joined("java", "import org.junit.jupiter.api.Test;\n@BeforeEach void s(){}")
    assert "TestNG" in joined("java", "import org.testng.annotations.Test;\n@Test public void t(){}")


def test_java_without_page_objects_says_so_instead_of_inventing_them():
    rules = joined("java", "import org.junit.Test;\nclass T { @Test void t(){ driver.findElement(By.id(\"x\")); } }")
    assert "findElement" in rules and "do not introduce page objects" in rules


def test_java_driver_factory_is_reused():
    rules = joined("java", "class T { void s(){ driver = DriverFactory.getDriver(); } }")
    assert "DriverFactory.getDriver()" in rules


def test_python_pytest_rules():
    code = ("import pytest\nfrom pages.login_page import LoginPage\n\n"
            "@pytest.mark.parametrize('u', ['a','b'])\n"
            "def test_login(page, base_url, u):\n    assert LoginPage(page)\n")
    rules = joined("python", code)
    assert "pytest-style" in rules and "page, base_url, u" in rules
    assert "parametrize" in rules and "pages.login_page" in rules


def test_python_unittest_rules():
    rules = joined("python", "import unittest\nclass T(unittest.TestCase):\n    def test_x(self):\n        self.assertTrue(1)\n")
    assert "unittest.TestCase" in rules and "pytest-style" not in rules


def test_csharp_framework_rules_are_not_mixed():
    assert "NUnit" in joined("c#", "[TestFixture] class T { [Test] public void A(){ Assert.That(1, Is.EqualTo(1)); } }")
    assert "xUnit" in joined("c#", "class T { [Fact] public void A(){ Assert.Equal(1,1); } }")
    assert "MSTest" in joined("c#", "[TestClass] class T { [TestMethod] public void A(){} }")


def test_unknown_language_adds_nothing():
    assert A._analyze_test_style("some code", "") == []
    assert A._analyze_test_style("some code", "ruby") == []


def test_java_project_brief_now_contains_a_real_style_contract(tmp_path):
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "EngageTests.java").write_text(JUNIT4)
    agent = A(_Stub(), {"automation_type": "ui"})
    prompt = asyncio.run(agent.process("mfa test", project_path=str(tmp_path),
                                       prepare_only=True))["__prompt__"]
    assert "STYLE CONTRACT — your generated test MUST follow" in prompt
    assert "Use JUnit 4 (org.junit)" in prompt
