# Quality Engineering Agentic Framework (QEAF)

An AI-powered framework that uses autonomous agents to automate the software testing process based on user-defined requirements.

## Overview

QEAF consists of three main agents:

1. **Test Case Generation Agent**: Converts plaintext or structured software requirements into structured test cases.
2. **Test Script Generator**: Transforms test cases into executable Selenium test scripts.
3. **Synthetic Test Data Generator**: Creates valid, edge-case, and randomized test data for the test cases.

## Features

- Configurable LLM Layer supporting OpenAI GPT-4, Google Gemini, and other LLMs
- Domain-specific requirement pattern support
- Any open source (ex Selenium WebDriver) test script generation
- Synthetic test data generation with CSV and JSON export
- Modular and extensible architecture
- Configuration via YAML or JSON
- Comprehensive logging and error handling
- Web-based UI for easy interaction with the framework

## Installation

```bash
pip install -e .
```

## Usage

### Command Line Interface

```bash
# Run the backend services (Do the cd to the folder 'Test Case Generation')
python -m quality_engineering_agentic_framework.web.api.endpoints 8080

# Run the web interface (from the folder 'Test Case Generation\quality_engineering_agentic_framework\web\ui')
python -m streamlit run app.py
```

### Web Interface

The framework includes a web-based UI that allows you to:

1. Configure LLM backends (OpenAI, Gemini)
2. Manage API keys securely
3. Edit prompt templates
4. Interact with agents through a user-friendly interface
5. View and download outputs

To start the web interface:

```bash
qeaf web
```

This will start both the API server and the Streamlit UI, and open your browser to the UI.

### Docker Deployment

You can also run the framework using Docker:

```bash
# Build and run using docker-compose
docker-compose up -d

# Or build and run manually
docker build -t qeaf .
docker run -p 8000:8000 -p 8501:8501 -v ./config:/app/config qeaf
```

### MCP Server (Use QEAF from any project via AI Chat)

QEAF can be exposed as an **MCP (Model Context Protocol) server**, allowing any AI assistant
(GitHub Copilot, Claude, Cursor, Windsurf) to call QEAF tools directly from a chat conversation —
no UI, no manual API calls.

#### Step 1 — Install dependencies

```bash
pip install -e .
pip install "mcp>=1.0.0" "starlette>=0.40.0,<0.48.0"
```

#### Step 2 — Set your OpenAI API key

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

#### Step 3 — Start the MCP server

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

Server will start at `http://localhost:8080/sse`. Keep this terminal running.

#### Step 4 — Connect from your IDE

---

##### VS Code

**1. Create `.vscode/mcp.json`** in your other repo:

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

**2. Enable MCP in VS Code settings (one time):**

- **Mac:** `Cmd+Shift+P` → Open User Settings JSON → add `"chat.mcp.enabled": true`
- **Windows:** `Ctrl+Shift+P` → Open User Settings JSON → add `"chat.mcp.enabled": true`

**3. Reload VS Code:**

- **Mac:** `Cmd+Shift+P` → Reload Window
- **Windows:** `Ctrl+Shift+P` → Reload Window

**4. Open GitHub Copilot Chat:**

- **Mac:** `Cmd+Shift+I`
- **Windows:** `Ctrl+Shift+I`

**5. Verify tools are loaded:** Click the `#` icon at the bottom of the Copilot Chat input — you should see all 5 QEAF tools listed.

---

##### IntelliJ IDEA / WebStorm / PyCharm

**1. Install GitHub Copilot plugin** (if not already installed):

`Settings` → `Plugins` → search `GitHub Copilot` → Install → Restart IDE

**2. Add the MCP server:**

`Settings` → `Tools` → `GitHub Copilot` → `MCP Servers` → click `+` → Add:

| Field | Value |
|-------|-------|
| Name | `qeaf` |
| Type | `SSE` |
| URL  | `http://localhost:8080/sse` |

Click **OK** and **Apply**.

**3. Open Copilot Chat in IntelliJ:**

- **Mac:** `Cmd+Shift+A` → search `GitHub Copilot Chat` → Enter
- **Windows:** `Ctrl+Shift+A` → search `GitHub Copilot Chat` → Enter

Or click the **Copilot icon** in the right sidebar.

**4. Verify tools are loaded:** Click the tools/`#` icon in the chat panel — QEAF tools should appear.

---

#### Step 5 — Use in Copilot Chat (same for VS Code and IntelliJ)

```
Use the generate_test_cases tool with requirements: "login feature"
and selected_documents: "my_requirements.txt"
```

#### Available MCP Tools

| Tool | What it does |
|------|-------------|
| `generate_test_cases` | Requirements → structured test cases (with RAG support) |
| `generate_test_scripts` | Test cases → executable Selenium scripts (Python/Java/JS/C#) |
| `generate_test_data` | Test cases → synthetic test data (JSON/CSV/SQL) |
| `generate_api_test_cases` | API endpoint → Java RestAssured test class |
| `add_requirement_document` | Copy a doc from any repo into the QEAF Knowledge Hub |

#### Adding requirement documents from another repo

```
# Step 1 — Add the document
Use the add_requirement_document tool with file_path: "/path/to/your-repo/docs/requirements.pdf"

# Step 2 — Generate test cases using it
Use the generate_test_cases tool with requirements: "login feature"
and selected_documents: "requirements.pdf"
```

---

#### Sample Prompts

**Generate test cases from plain text:**
```
Use the generate_test_cases tool with requirements:
"Users should be able to log in using email and password.
After 3 failed attempts the account should be locked for 30 minutes."
```

**Generate test cases from a requirement document:**
```
Use the generate_test_cases tool with requirements: "login and authentication feature"
and selected_documents: "requirements.txt"
```

**Generate test cases from a document in another repo:**
```
Use the add_requirement_document tool with file_path: "/Users/you/my-project/docs/requirements.pdf"

Use the generate_test_cases tool with requirements: "checkout flow"
and selected_documents: "requirements.pdf"
```

**Generate Python pytest scripts from test cases:**
```
Use the generate_test_scripts tool with the test cases above,
language: "python", framework: "pytest", browser: "chrome"
```

**Generate Java TestNG scripts from test cases:**
```
Use the generate_test_scripts tool with the test cases above,
language: "java", framework: "testng", browser: "chrome"
```

**Generate JavaScript Cypress scripts from test cases:**
```
Use the generate_test_scripts tool with the test cases above,
language: "javascript", framework: "cypress", browser: "chrome"
```

**Generate test data for test cases:**
```
Use the generate_test_data tool with the test cases above,
output_format: "json", data_variations: 5, include_edge_cases: true
```

**Generate test data in CSV format:**
```
Use the generate_test_data tool with the test cases above,
output_format: "csv", data_variations: 10
```

**Generate API test cases:**
```
Use the generate_api_test_cases tool with
base_url: "https://api.example.com",
endpoint: "/api/v1/login",
method: "POST",
body: '{"email": "user@example.com", "password": "secret"}',
auth: "Bearer token"
```

**Full workflow in one go:**
```
Use the generate_test_cases tool with requirements: "user registration feature"
and selected_documents: "requirements.txt",
then use generate_test_scripts with language: "python" and framework: "pytest",
then use generate_test_data with output_format: "json"
```

### Configuration

Create a `config.yaml` file in the `config/` directory:

```yaml
llm:
  provider: openai  # or gemini
  model: gpt-4
  api_key: your_api_key_here

agents:
  test_case_generation:
    prompt_template: "templates/test_case_generation_prompt.txt"
    output_format: "gherkin"
  test_script_generator:
    browser: chrome
  test_data_generator:
    output_format: json  # or csv
```

## Web Interface Walkthrough

### 1. LLM Configuration

In the sidebar, you can:
- Select the LLM provider (OpenAI or Gemini)
- Choose the model
- Enter your API key
- Adjust temperature and max tokens

### 2. Test Case Generation

In the "Test Case Generation" tab:
- Configure the agent (output format, prompt template)
- Enter requirements text or upload a file
- Generate test cases
- View and download the results

### 3. Test Script Generation

In the "Test Script Generation" tab:
- Configure the agent (framework, browser, prompt template)
- Use test cases from the previous step or upload a file
- Generate test scripts
- View and download individual scripts or all as a ZIP

### 4. Test Data Generation

In the "Test Data Generation" tab:
- Configure the agent (output format, data variations, edge cases)
- Use input from previous steps or upload a file
- Generate test data
- View and download the results in JSON or CSV format

## License

[Your License]
