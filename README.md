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
pip install "mcp>=1.0.0" "starlette>=0.40.0,<0.48.0"
```

### Step 2 — Set your API key

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
| `standalone_automation` | Reads your open project, reuses existing methods, generates UI/API automation for any framework |
| `analyse_tests` | Analyses test results and failures to surface actionable insights |
| `browser_qa` | Drives browser-based QA checks and generates browser automation scripts |

## Tool Feature Flags

Each tool has an on/off flag in [`mcp_tool_flags.py`](mcp_tool_flags.py). By default only `standalone_automation` is enabled.

**Permanent — edit defaults** in `mcp_tool_flags.py`:

```python
DEFAULT_FLAGS = {
    "standalone_automation": True,
    "analyse_tests": False,
    "browser_qa": False,
}
```

**Runtime — set environment variable:**

```bash
QEAF_ENABLE_ANALYSE_TESTS=true \
MCP_TRANSPORT=sse MCP_HOST=0.0.0.0 MCP_PORT=8080 \
python mcp_server.py
```

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
