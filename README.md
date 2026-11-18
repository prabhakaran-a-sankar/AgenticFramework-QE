# Quality Engineering Agentic Framework (QEAF) — MCP Server

An AI-powered framework that exposes quality engineering agents as MCP (Model Context Protocol) tools, allowing any AI assistant (GitHub Copilot, Claude, Cursor, Windsurf) to drive test automation directly from a chat conversation.

## Agents

| Agent | Description |
|-------|-------------|
| **Standalone Automation Agent** | Reads your open project, reuses its existing methods, and generates UI/API automation for any framework |
| **Test Analyser Agent** | Analyses test results, failures, and coverage to surface actionable insights |
| **Browser QA Agent** | Drives browser-based quality checks and generates browser automation scripts |

## MCP Server Setup

### Step 1 — Install dependencies

```bash
pip install -e .
pip install "mcp>=1.27,<2" "starlette>=0.40.0,<0.48.0"
```

### Step 2 — (Optional) Set a fallback model key

**You only need this if your MCP client cannot run model requests for the server** (no MCP sampling)
*and* you want the server to write the code itself. GitHub Copilot in VS Code supports sampling, so
it needs no key. Clients without sampling (for example the Claude desktop app) work with no key too:
the server returns a brief and the assistant writes the code — see [Generation modes](#generation-modes).

**Mac/Linux:**
```bash
export OPENAI_API_KEY="sk-your-key-here"
```

**Windows (Command Prompt):**
```cmd
set OPENAI_API_KEY=sk-your-key-here
```

**Windows (PowerShell):**
```powershell
$env:OPENAI_API_KEY="sk-your-key-here"
```

### Step 3 — Start the MCP server

**Mac/Linux:**
```bash
lsof -ti:8080 | xargs kill -9 2>/dev/null; sleep 1 && \
MCP_TRANSPORT=sse MCP_HOST=0.0.0.0 MCP_PORT=8080 \
LLM_PROVIDER=openai LLM_MODEL=gpt-4o \
python mcp_server.py
```

**Windows (Command Prompt):**
```cmd
FOR /F "tokens=5" %a IN ('netstat -aon ^| find ":8080"') DO taskkill /F /PID %a 2>nul
set MCP_TRANSPORT=sse
set MCP_HOST=0.0.0.0
set MCP_PORT=8080
set LLM_PROVIDER=openai
set LLM_MODEL=gpt-4o
python mcp_server.py
```

**Windows (PowerShell):**
```powershell
Stop-Process -Id (Get-NetTCPConnection -LocalPort 8080 -ErrorAction SilentlyContinue).OwningProcess -Force -ErrorAction SilentlyContinue
$env:MCP_TRANSPORT="sse"; $env:MCP_HOST="0.0.0.0"; $env:MCP_PORT="8080"
$env:LLM_PROVIDER="openai"; $env:LLM_MODEL="gpt-4o"
python mcp_server.py
```

Server starts at `http://localhost:8080/sse`. Keep this terminal running.

### Step 4 — Connect from your IDE

#### VS Code

Create `.vscode/mcp.json` in your project:

```json
{
  "servers": {
    "qeaf": {
      "type": "sse",
      "url": "http://localhost:8080/sse"
    }
  }
}
```

Enable MCP in VS Code settings (`Cmd+Shift+P` / `Ctrl+Shift+P` → Open User Settings JSON):
```json
"chat.mcp.enabled": true
```

#### IntelliJ / PyCharm / WebStorm

`Settings` → `Tools` → `GitHub Copilot` → `MCP Servers` → `+`:

| Field | Value |
|-------|-------|
| Name | `qeaf` |
| Type | `SSE` |
| URL  | `http://localhost:8080/sse` |

## Available MCP Tools

| Tool | What it does |
|------|-------------|
| `standalone_automation` | Reads your project, reuses existing methods, and generates UI/API automation for any framework. Review-first: returns files, writes nothing unless `apply=true`. |
| `validate_generated_code` | Checks (syntax, brackets) and formats files an assistant wrote. Read-only, makes no model calls. Used after the brief mode below. Pass `project_path` or `existing_files` to also run the reuse check (see below). |

| `analyse_tests` | Reads an existing test project (read-only) and converts each test into structured test cases — `bdd`, `plain` or `step_by_step` — exported as an `.xlsx`. Needs a model (client sampling or a configured key); without one it returns the inventory of tests found. The file is saved outside your project (`QEAF_OUTPUT_DIR`, else the system temp folder, or `save_to`). |

The Browser QA agent is included in the codebase but is **not yet exposed as an MCP tool**.

All tools return the usual human-readable report **plus** the same information as machine-readable
`structuredContent` (mode, files, validation results, export path…), so scripts and CI can consume the
output without parsing text.

### What it learns from your project

For `standalone_automation` the server studies the project before building the brief: language and
framework (from marker files such as `pom.xml` / `package.json`, else the most common source
extension), folder layout, class and method signatures, the most relevant source files (full source,
up to 3), and **one existing test as the style example** — the test whose file name best matches your
task, else the first test file. From that example it derives explicit style rules, for example:

| Language | Rules derived from the example |
|----------|--------------------------------|
| JavaScript / Playwright | test signature and fixtures, `describe` grouping, direct `page.*` calls, imported selector constants, `testData` reuse |
| Java | JUnit 4 / JUnit 5 / TestNG (never mixed), assertion style, how the WebDriver is created, page objects vs raw `findElement`, explicit waits, `@Before`/`@After` structure, `testXxx` naming |
| Python | pytest vs unittest, fixtures used as parameters, `parametrize`, page-object imports, Playwright `expect` / async |
| C# | NUnit vs xUnit vs MSTest (never mixed), assertion style, page objects |

If the project has nothing to learn from, the brief asks for professional best-practice standards instead.

### Reuse first, create only when nothing fits

The brief gives the model a **ranked catalog of the project's existing classes and methods** (most
relevant to the task first) and a short protocol:

1. **Reuse first** — for every action or check in the test, call an existing method if one fits the purpose.
2. **Create only when nothing fits** — add the new method to the existing class that owns that page or
   area (returning that class's complete updated file), named and written like its siblings; create a
   new class only when no class owns the area.
3. Never call a method on an existing class that isn't listed, unless it is added in the same answer.
4. End with a **REUSE REPORT** (`REUSED:` / `CREATED:` lines), which the tool shows to the user.

After generation the server runs a **reuse check**: it flags calls such as `loginPage.clickSubmit()`
where `LoginPage` is known but `clickSubmit` exists neither in your project nor in the generated files,
and suggests the closest existing method. These are warnings, not proof — classes that extend a base class
the server cannot see are never flagged. With `validate_generated_code`, pass `project_path` (or
`existing_files`) to run the same check on code an assistant wrote. Supported: Java, Python,
JavaScript/TypeScript, C# and Gherkin.

**Fixtures.** Playwright fixtures (`base.extend({ loginPage: … })`) and pytest fixtures (`@pytest.fixture`)
are catalogued. The brief lists them ("ask for them as test parameters, don't construct them yourself"), and
the reuse check follows them: in `async ({ loginPage }) => …` or `def test_x(login_page)`, a call such as
`loginPage.signIn()` is checked against the fixture's page class.

**Gherkin / BDD.** When a project has both `.feature` files and step definitions (Cucumber for Java, JS or
C#/SpecFlow, or Python behave), the agent switches to scenario mode:

- the brief lists the **existing step phrases** (most relevant first) and uses a `.feature` file as the style
  example, with rules derived from it (`Scenario Outline`, `Background`, tags, first-person wording, quoted
  parameters, `And`/`But`, the *As a / I want / So that* header);
- the model is told to build scenarios from those exact phrases, and only if none fits to add **one new step
  phrase plus its step definition** in the steps file that owns that area, calling existing page-object methods;
- the reuse check flags any generated step that matches no existing or newly added step definition (it
  understands Cucumber expressions such as `{string}` / `{int}`, regex steps, behave/parse placeholders and
  `Scenario Outline` `<placeholders>`), and `.feature` files get a structure check (missing `Feature:`,
  an Outline without `Examples:`, ragged tables).

Not supported: Robot Framework, Ruby, Go and Kotlin projects (no reader for them), and Cypress custom
commands (`Cypress.Commands.add`).

### Slash command (MCP prompt)

Clients that support MCP prompts show a `qeaf_generate` command. It takes `task`, an optional
`project_path`, and `automation_type` (`ui` | `api` | `both`), and tells the assistant exactly how to use
the tools: gather context, call `standalone_automation` (never `apply=true`), validate, and apply each
file through the editor so you review every diff.

### Secret redaction

Before project source, example tests, page snapshots or test bodies go into a prompt or brief, the
server masks secret-like values — well-known token formats (AWS, GitHub, OpenAI/Anthropic, Slack,
Google, JWT, private keys), bearer tokens, credentials in URLs, quoted `password` / `secret` /
`token` / `api_key` assignments, and unquoted `.env`-style lines. Numbers and booleans are left alone.
When anything is masked, the output says how many values were. It is **on by default**; set
`QEAF_REDACT_SECRETS=false` to turn it off. This is a safety net, not a guarantee — keep real secrets
out of source control.

## Generation modes

`standalone_automation` needs a model to write the code. Which one it uses depends on the client:

| Client | What happens |
|--------|--------------|
| **Supports MCP sampling** (GitHub Copilot in VS Code) | The server asks the client's model to write the code, then validates and fixes it. No key needed. |
| **No sampling, but a key is configured** (`LLM_PROVIDER` + `GITHUB_TOKEN` / `OPENAI_API_KEY` / `GEMINI_API_KEY`) | The server calls that provider, then validates and fixes the code. |
| **No sampling and no key** (for example the Claude desktop app) | **Brief mode:** the server returns a detailed brief — your project's real code, style rules and the task. The assistant writes the files, checks them with `validate_generated_code`, and applies them. |

You can force brief mode on any client by passing `prepare_only=true`.

## Tool Feature Flags

Each tool has an on/off flag in [`mcp_tool_flags.py`](mcp_tool_flags.py). `standalone_automation` and `validate_generated_code` are on by default, and `test_analyser` turns the `analyse_tests` tool on or off.

**Permanent — edit defaults** in `mcp_tool_flags.py`:

```python
DEFAULT_FLAGS = {
    "standalone_automation": True,
    "test_analyser": True,
    "validate_generated_code": True,
}
```

**Runtime — set environment variable:**

```bash
QEAF_ENABLE_VALIDATE_GENERATED_CODE=false \
MCP_TRANSPORT=sse MCP_HOST=0.0.0.0 MCP_PORT=8080 \
python mcp_server.py
```

## Restricting Project Folders (Optional)

By default the server accepts **any** `project_path` the client sends. For shared servers, CI, or any
setup where you want to limit what the tool can read and write, set an allow-list. **It is off by
default** — if you do nothing, behaviour is unchanged.

Set `QEAF_ALLOWED_ROOTS` to one or more folders. Separate several folders with `:` on Mac/Linux or
`;` on Windows.

**In your MCP client config** (stdio — recommended):

```json
{
  "mcpServers": {
    "qeaf": {
      "command": "/path/to/python",
      "args": ["/path/to/mcp_server.py"],
      "env": { "QEAF_ALLOWED_ROOTS": "/Users/you/projects:/Users/you/work" }
    }
  }
}
```

**Or when starting the server yourself:**

```bash
# Mac/Linux
QEAF_ALLOWED_ROOTS="/Users/you/projects:/Users/you/work" python mcp_server.py
```
```cmd
:: Windows (Command Prompt)
set QEAF_ALLOWED_ROOTS=C:\projects;C:\work
python mcp_server.py
```

| Setting | Behaviour |
|---------|-----------|
| Not set, or empty | Any folder is accepted (default) |
| Set | Only folders **inside** the listed roots are accepted. Anything else is refused with a clear message and logged. |

Notes:
- The check applies to both reading the project and writing generated files (`apply=true`).
- Symlinks and `..` are resolved before checking, so `/allowed/../elsewhere` is refused.
- Sub-folders of a listed root are allowed.
- On startup the server logs the active setting. Look for `Project allow-list:` in the server log.
- It does not affect `existing_files` mode, where the client sends file contents and the server reads no disk.

## Configuration

`config/config.yaml`:

```yaml
llm:
  provider: openai  # or gemini
  model: gpt-4o
  api_key: your_api_key_here
```

## License

[Your License]
