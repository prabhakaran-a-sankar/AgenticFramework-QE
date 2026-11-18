import asyncio

import pytest

from quality_engineering_agentic_framework.agents.automation_agent import AutomationAgent
from quality_engineering_agentic_framework.llm.llm_interface import LLMInterface
from quality_engineering_agentic_framework.utils.redaction import (
    maybe_redact,
    redact_secrets,
    redaction_enabled,
)


@pytest.mark.parametrize("secret", [
    "AKIAABCDEFGHIJKLMNOP",
    "ghp_" + "a1B2c3D4e5F6g7H8i9J0k1L2m3N4o5P6q7R8",
    "sk-" + "abcdefghijklmnopqrstuvwxyz0123456789",
    "xoxb-1234567890-abcdefghij",
    "AIza" + "SyA-1234567890abcdefghijklmnopqrstu",     # 35 chars after the prefix, like real keys
    "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.abcdefghijk123456",
])
def test_known_token_formats_are_redacted(secret):
    out, n = redact_secrets(f"value = {secret} # end")
    assert secret not in out and n >= 1


def test_private_key_block_is_redacted():
    key = "-----BEGIN RSA PRIVATE KEY-----\nMIIabc\ndef\n-----END RSA PRIVATE KEY-----"
    out, n = redact_secrets(f"before\n{key}\nafter")
    assert "MIIabc" not in out and "before" in out and "after" in out and n == 1


def test_quoted_credential_assignments_are_redacted_in_several_languages():
    for line in ['String password = "Sup3rS3cret!";', "api_key = 'abcd1234efgh'",
                 '{"client_secret": "zzzzzzzz"}', 'token: "abcdef123456"']:
        out, n = redact_secrets(line)
        assert "<REDACTED>" in out and n == 1, line


def test_env_style_lines_are_redacted_but_numbers_and_booleans_are_not():
    out, n = redact_secrets("PASSWORD=hunter2hunter2\nAPI_TOKEN: abcdef123456\n"
                            "TOKEN_TTL=3600000\nUSE_TOKEN=true")
    assert "hunter2" not in out and "abcdef123456" not in out
    assert "TOKEN_TTL=3600000" in out and "USE_TOKEN=true" in out
    assert n == 2


def test_bearer_token_and_url_credentials_are_redacted():
    out, _ = redact_secrets("Authorization: Bearer abcdefghijklmnop1234567890")
    assert "abcdefghijklmnop" not in out and "Bearer" in out
    out, _ = redact_secrets("postgres://admin:s3cr3tpass@db.local/app")
    assert "s3cr3tpass" not in out and "admin" in out and "@db.local" in out


def test_ordinary_code_is_left_alone():
    code = ('driver.get("https://engage.accenture.com/");\n'
            'ssoPage.login("validUsername", "validPassword");\n'
            "password = getPassword()\nmax_tokens = 4000\n")
    out, n = redact_secrets(code)
    assert out == code and n == 0


def test_switch_off_with_environment_variable(monkeypatch):
    monkeypatch.setenv("QEAF_REDACT_SECRETS", "false")
    assert redaction_enabled() is False
    assert maybe_redact('password = "Sup3rS3cret!"') == 'password = "Sup3rS3cret!"'
    monkeypatch.setenv("QEAF_REDACT_SECRETS", "true")
    assert "Sup3rS3cret" not in maybe_redact('password = "Sup3rS3cret!"')


class _Stub(LLMInterface):
    def __init__(self):
        self.prompts = []

    async def generate(self, prompt, system_message=None, temperature=None, max_tokens=None):
        self.prompts.append(prompt)
        return "```java:A.java\nclass A {}\n```"

    async def generate_with_json_output(self, *a, **k):
        return {}

    def get_provider_name(self):
        return "stub"


FILES = {
    "pom.xml": "<project/>",
    "pages/LoginPage.java": ('package pages;\npublic class LoginPage {\n'
                             '  static String apiKey = "abcdEFGH12345678";\n'
                             '  public void clickLogin() {}\n}\n'),
    "tests/LoginTest.java": "package tests;\nimport org.junit.Test;\npublic class LoginTest {}\n",
}


def test_agent_masks_secrets_in_the_prompt_and_reports_the_count(monkeypatch):
    monkeypatch.setenv("QEAF_REDACT_SECRETS", "true")
    stub = _Stub()
    agent = AutomationAgent(stub, {})
    asyncio.run(agent.process("login test", existing_files=FILES))
    assert "abcdEFGH12345678" not in stub.prompts[0]
    assert "class LoginPage" in stub.prompts[0]          # the code itself is still there
    assert agent.last_redactions >= 1


def test_agent_leaves_prompt_untouched_when_redaction_is_off(monkeypatch):
    monkeypatch.setenv("QEAF_REDACT_SECRETS", "false")
    stub = _Stub()
    agent = AutomationAgent(stub, {})
    asyncio.run(agent.process("login test", existing_files=FILES))
    assert "abcdEFGH12345678" in stub.prompts[0]
    assert agent.last_redactions == 0
