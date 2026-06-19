# QA Browser Agent

An open-source AI-powered QA testing agent — write tests in plain English, get back screenshots, video recordings, and structured bug reports. Supports any web or mobile platform and any LLM provider.

---

## Table of Contents

1. [What It Does](#what-it-does)
2. [Architecture](#architecture)
3. [Supported Platforms](#supported-platforms)
4. [Supported LLM Providers](#supported-llm-providers)
5. [Quick Start](#quick-start)
6. [CLI Examples](#cli-examples)
7. [API Server + Worker Examples](#api-server--worker-examples)
8. [Mobile Testing Examples](#mobile-testing-examples)
9. [Integrations](#integrations)
10. [Storage Backends](#storage-backends)
11. [Environment Variables Reference](#environment-variables-reference)
12. [Project Structure](#project-structure)

---

## What It Does

- You describe a test in plain English (e.g. *"Go to the login page and verify the submit button is visible"*)
- The AI agent opens a real browser (or mobile device), navigates, clicks, types, and asserts — step by step
- Every step is captured: screenshot, DOM snapshot, action taken
- A full HTML + JSON report is generated with screenshots, video, and all bugs found
- Integrates with GitHub PRs, Slack, and webhooks for CI/CD

---

## Architecture

```
browser_qa_agent/
├── config.py            # All env-based settings (LLM, DB, storage, integrations)
├── browser.py           # Playwright async browser controller (desktop web)
├── mobile_browser.py    # Playwright mobile emulation + Appium native controller
├── llm.py               # LLM client — reads provider from env, delegates to providers/
├── planner.py           # Agentic loop: screenshot → LLM → action → repeat
├── executor.py          # Executes actions, captures traces
├── reporter.py          # Generates JSON + HTML reports, uploads artifacts
│
├── providers/           # Pluggable LLM providers
│   ├── base.py          # Abstract LLMProvider + shared tool schemas
│   ├── anthropic_provider.py   # Claude (Anthropic)
│   ├── openai_provider.py      # GPT-4o / Azure OpenAI
│   ├── gemini_provider.py      # Google Gemini
│   └── ollama_provider.py      # Local Ollama (llava, llama3.2-vision)
│
├── storage/             # Cloud-agnostic artifact storage
│   ├── local.py         # Local filesystem (dev)
│   └── s3.py            # AWS S3 / Cloudflare R2 / MinIO / GCS
│
├── workers/             # Celery async job queue
│   ├── celery_app.py    # Celery + Redis config
│   └── test_runner.py   # Main Celery task
│
├── api/                 # FastAPI REST API
│   └── routes/
│       ├── projects.py  # CRUD: projects
│       ├── tests.py     # CRUD: test cases
│       ├── runs.py      # Trigger + poll runs
│       ├── reports.py   # Fetch reports
│       └── webhooks.py  # GitHub + generic inbound webhooks
│
├── integrations/
│   ├── github.py        # GitHub App: PR checks
│   ├── slack.py         # Slack notifications
│   └── webhooks.py      # Outbound webhooks
│
├── cli/
│   └── main.py          # Typer CLI: run, serve, worker commands
│
├── models/              # SQLAlchemy DB models
├── db/                  # Async DB engine + session
├── requirements.txt     # Dependencies for this module only
└── .env.example         # All env vars with comments
```

---

## Supported Platforms

| Platform | How | Extra Setup |
|----------|-----|-------------|
| Desktop Web | Playwright Chromium | None |
| Mobile Web | Playwright + device emulation | None — uses built-in device profiles |
| Native iOS | Appium | Appium server + iOS simulator or real device |
| Native Android | Appium | Appium server + Android emulator or real device |

**Mobile device presets (for mobile_web):**

| Key | Device |
|-----|--------|
| `iphone_14` | iPhone 14 |
| `iphone_14_pro` | iPhone 14 Pro |
| `iphone_se` | iPhone SE |
| `pixel_7` | Pixel 7 |
| `galaxy_s23` | Galaxy S23 |
| `ipad_pro` | iPad Pro 11 |
| `ipad_mini` | iPad Mini |

---

## Supported LLM Providers

| Provider | `LLM_PROVIDER` value | Vision support | Notes |
|----------|---------------------|----------------|-------|
| Anthropic Claude | `anthropic` | Yes | Best results |
| OpenAI GPT-4o | `openai` | Yes | |
| Azure OpenAI | `azure_openai` | Yes | Set endpoint + api_version |
| Google Gemini | `gemini` | Yes | |
| Ollama (local) | `ollama` | Yes (llava) | No API key needed |

---

## Quick Start

### 1. Install dependencies

```bash
cd quality_engineering_agentic_framework/agents/browser_qa_agent

pip install -r requirements.txt
playwright install chromium
```

### 2. Configure environment

```bash
cp .env.example .env
```

Open `.env` and set **at minimum**:

```
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-...
```

Or export inline:

```bash
export LLM_PROVIDER=anthropic
export ANTHROPIC_API_KEY=sk-ant-...
export STORAGE_BACKEND=local
```

### 3. Run your first test (no server needed)

```bash
# From the repo root
cd /path/to/AgenticFramework-QE

python -m quality_engineering_agentic_framework.agents.browser_qa_agent.cli.main run \
  "https://example.com" \
  "Navigate to the homepage and verify the heading says Example Domain"
```

---

## CLI Examples

### Basic web test

```bash
python -m quality_engineering_agentic_framework.agents.browser_qa_agent.cli.main run \
  "https://wikipedia.org" \
  "Search for Python programming language and verify the first result opens"
```

### Non-headless (watch the browser)

```bash
python -m quality_engineering_agentic_framework.agents.browser_qa_agent.cli.main run \
  "https://github.com" \
  "Verify the Sign In button is visible on the homepage" \
  --no-headless
```

### More steps for complex flows

```bash
python -m quality_engineering_agentic_framework.agents.browser_qa_agent.cli.main run \
  "https://your-staging-app.com" \
  "Go to the login page, enter test@example.com and password123, click login, and verify the dashboard loads" \
  --max-steps 20
```

### Mobile web test (iPhone 14 emulation)

```bash
python -m quality_engineering_agentic_framework.agents.browser_qa_agent.cli.main run \
  "https://example.com" \
  "Verify the page loads correctly and the heading is visible on mobile" \
  --platform mobile_web \
  --device iphone_14
```

### Switch LLM provider at runtime

```bash
# Use OpenAI instead of Anthropic
export OPENAI_API_KEY=sk-...

python -m quality_engineering_agentic_framework.agents.browser_qa_agent.cli.main run \
  "https://example.com" \
  "Verify the homepage loads" \
  --provider openai \
  --model gpt-4o
```

```bash
# Use local Ollama (must have Ollama + llava running)
python -m quality_engineering_agentic_framework.agents.browser_qa_agent.cli.main run \
  "https://example.com" \
  "Verify the homepage loads" \
  --provider ollama \
  --model llava
```

---

## API Server + Worker Examples

### Start everything

**Terminal 1 — Redis (required for Celery):**
```bash
redis-server
```

**Terminal 2 — Celery worker:**
```bash
python -m quality_engineering_agentic_framework.agents.browser_qa_agent.cli.main worker
```

**Terminal 3 — API server:**
```bash
python -m quality_engineering_agentic_framework.agents.browser_qa_agent.cli.main serve
# API available at http://localhost:8080
# Docs at http://localhost:8080/docs
```

---

### Full example flow via API

#### Step 1 — Create a project

```bash
curl -X POST http://localhost:8080/api/v1/projects/ \
  -H "Content-Type: application/json" \
  -d '{
    "name": "My Web App",
    "base_url": "https://example.com",
    "description": "Production smoke tests"
  }'
```

Response:
```json
{
  "id": "abc-123",
  "name": "My Web App",
  "base_url": "https://example.com",
  "description": "Production smoke tests",
  "config": {}
}
```

#### Step 2 — Create a test case

```bash
curl -X POST http://localhost:8080/api/v1/projects/abc-123/tests/ \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Homepage heading check",
    "nl_description": "Navigate to the homepage and verify the main heading is visible",
    "tags": ["smoke", "homepage"],
    "max_steps": 10
  }'
```

Response:
```json
{
  "id": "tc-456",
  "project_id": "abc-123",
  "title": "Homepage heading check",
  "nl_description": "Navigate to the homepage and verify the main heading is visible",
  "tags": ["smoke", "homepage"],
  "max_steps": 10
}
```

#### Step 3 — Trigger a run

```bash
# Desktop web
curl -X POST http://localhost:8080/api/v1/runs/ \
  -H "Content-Type: application/json" \
  -d '{
    "test_case_id": "tc-456",
    "platform": "web",
    "triggered_by": "api"
  }'
```

```bash
# Mobile web (iPhone 14)
curl -X POST http://localhost:8080/api/v1/runs/ \
  -H "Content-Type: application/json" \
  -d '{
    "test_case_id": "tc-456",
    "platform": "mobile_web",
    "mobile_config": {"device": "iphone_14"}
  }'
```

Response:
```json
{
  "id": "run-789",
  "test_case_id": "tc-456",
  "status": "queued",
  "triggered_by": "api"
}
```

#### Step 4 — Poll for run status

```bash
curl http://localhost:8080/api/v1/runs/run-789
```

Response when done:
```json
{
  "id": "run-789",
  "status": "passed",
  "triggered_by": "api"
}
```

#### Step 5 — Get the report

```bash
curl http://localhost:8080/api/v1/reports/run-789
```

Response:
```json
{
  "id": "rpt-001",
  "run_id": "run-789",
  "bugs_found": 0,
  "summary": "Completed 3 steps. Bugs: 0",
  "findings": [],
  "html_report_url": "file:///artifacts/runs/run-789/report.html",
  "video_url": "file:///artifacts/runs/run-789/video.webm",
  "artifact_urls": {
    "json": "file:///artifacts/runs/run-789/report.json",
    "html": "file:///artifacts/runs/run-789/report.html"
  }
}
```

---

## Mobile Testing Examples

### Mobile web (no extra setup — uses Playwright device emulation)

```bash
# Via CLI
python -m quality_engineering_agentic_framework.agents.browser_qa_agent.cli.main run \
  "https://m.facebook.com" \
  "Verify the login form is visible on the Facebook mobile site" \
  --platform mobile_web \
  --device pixel_7

# Via API
curl -X POST http://localhost:8080/api/v1/runs/ \
  -H "Content-Type: application/json" \
  -d '{
    "test_case_id": "tc-456",
    "platform": "mobile_web",
    "mobile_config": {"device": "galaxy_s23"}
  }'
```

### Native Android (Appium required)

1. Install Appium:
```bash
npm install -g appium
appium driver install uiautomator2
appium &   # starts on port 4723
```

2. Start an Android emulator or connect a real device.

3. Trigger via API:
```bash
curl -X POST http://localhost:8080/api/v1/runs/ \
  -H "Content-Type: application/json" \
  -d '{
    "test_case_id": "tc-456",
    "platform": "mobile_native",
    "appium_config": {
      "appium_url": "http://localhost:4723",
      "desired_caps": {
        "platformName": "Android",
        "platformVersion": "13",
        "deviceName": "emulator-5554",
        "app": "/path/to/your-app.apk",
        "automationName": "UiAutomator2"
      }
    }
  }'
```

### Native iOS (Appium required)

```bash
appium driver install xcuitest
```

```bash
curl -X POST http://localhost:8080/api/v1/runs/ \
  -H "Content-Type: application/json" \
  -d '{
    "test_case_id": "tc-456",
    "platform": "mobile_native",
    "appium_config": {
      "appium_url": "http://localhost:4723",
      "desired_caps": {
        "platformName": "iOS",
        "platformVersion": "17.0",
        "deviceName": "iPhone 15 Simulator",
        "app": "/path/to/your-app.app",
        "automationName": "XCUITest"
      }
    }
  }'
```

---

## Integrations

### GitHub App (auto-run on pull requests)

1. Create a GitHub App at https://github.com/settings/apps/new
   - Permissions: `Checks: Read & Write`, `Pull requests: Read`
   - Webhook URL: `https://your-domain/api/v1/webhooks/github`
2. Set in `.env`:
   ```
   GITHUB_APP_ID=123456
   GITHUB_PRIVATE_KEY=<PEM content>
   GITHUB_WEBHOOK_SECRET=your-secret
   ```
3. In your project config, set the repo:
   ```bash
   curl -X POST http://localhost:8080/api/v1/projects/ \
     -d '{"name": "My App", "base_url": "https://staging.myapp.com",
          "config": {"github_repo": "myorg/myrepo"}}'
   ```
4. Now every PR open/push automatically triggers all test cases and posts results as GitHub Checks.

### Slack notifications

```
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...
```

Message sent on every run completion:
```
✅ QA Run Complete
Test: Homepage heading check
Status: PASSED
Bugs found: 0
View Report → https://...
```

### Generic webhook (CI/CD trigger)

Trigger all tests for a project from any CI system:

```bash
curl -X POST http://your-qa-agent/api/v1/webhooks/trigger \
  -H "Content-Type: application/json" \
  -d '{"project_id": "abc-123"}'
```

---

## Storage Backends

| Backend | `STORAGE_BACKEND` | How to configure |
|---------|-------------------|-----------------|
| Local filesystem | `local` | `STORAGE_LOCAL_PATH=./artifacts` |
| AWS S3 | `s3` | Set `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `S3_BUCKET` |
| Cloudflare R2 | `s3` | `S3_ENDPOINT_URL=https://<account>.r2.cloudflarestorage.com` |
| MinIO (self-hosted) | `s3` | `S3_ENDPOINT_URL=http://localhost:9000` |
| GCS | `s3` | Use GCS S3-interop endpoint |

---

## Environment Variables Reference

```bash
# ── LLM ──────────────────────────────────────────────────────────────
LLM_PROVIDER=anthropic           # anthropic | openai | azure_openai | gemini | ollama
LLM_MODEL=claude-sonnet-4-6     # model name for the chosen provider

ANTHROPIC_API_KEY=sk-ant-...    # for LLM_PROVIDER=anthropic
OPENAI_API_KEY=sk-...           # for LLM_PROVIDER=openai or azure_openai
AZURE_OPENAI_ENDPOINT=https://  # for azure_openai
AZURE_OPENAI_API_VERSION=...    # for azure_openai, e.g. 2024-02-15-preview
GEMINI_API_KEY=...              # for LLM_PROVIDER=gemini
OLLAMA_BASE_URL=http://localhost:11434  # for LLM_PROVIDER=ollama

MAX_AGENT_STEPS=30              # max steps per test run

# ── Database ─────────────────────────────────────────────────────────
DATABASE_URL=sqlite+aiosqlite:///./qa_agent.db   # dev (SQLite)
# DATABASE_URL=postgresql+asyncpg://user:pass@host/db   # prod (Postgres)

# ── Job Queue ────────────────────────────────────────────────────────
REDIS_URL=redis://localhost:6379/0

# ── Artifact Storage ─────────────────────────────────────────────────
STORAGE_BACKEND=local            # local | s3
STORAGE_LOCAL_PATH=./artifacts

S3_BUCKET=qa-artifacts
S3_ENDPOINT_URL=                 # blank=AWS; set for R2/MinIO/GCS
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
AWS_REGION=us-east-1

# ── GitHub App ───────────────────────────────────────────────────────
GITHUB_APP_ID=
GITHUB_PRIVATE_KEY=
GITHUB_WEBHOOK_SECRET=

# ── Slack ────────────────────────────────────────────────────────────
SLACK_WEBHOOK_URL=

# ── API Server ───────────────────────────────────────────────────────
API_HOST=0.0.0.0
API_PORT=8080
SECRET_KEY=change-me-in-production
```

---

## Project Structure (full)

```
browser_qa_agent/
├── .env.example             ← copy to .env and fill in your keys
├── requirements.txt         ← pip install -r requirements.txt
├── README.md                ← this file
│
├── config.py                ← all settings read from env
├── browser.py               ← Playwright desktop browser
├── mobile_browser.py        ← Playwright mobile + Appium native
├── llm.py                   ← LLM client (wraps providers/)
├── planner.py               ← agentic loop
├── executor.py              ← action execution + trace capture
├── reporter.py              ← HTML + JSON report generator
│
├── providers/
│   ├── __init__.py          ← get_provider() factory
│   ├── base.py              ← LLMProvider ABC + tool schemas
│   ├── anthropic_provider.py
│   ├── openai_provider.py
│   ├── gemini_provider.py
│   └── ollama_provider.py
│
├── storage/
│   ├── __init__.py          ← get_storage() factory
│   ├── base.py
│   ├── local.py
│   └── s3.py
│
├── workers/
│   ├── celery_app.py
│   └── test_runner.py
│
├── api/
│   ├── main.py              ← FastAPI app
│   └── routes/
│       ├── projects.py
│       ├── tests.py
│       ├── runs.py
│       ├── reports.py
│       └── webhooks.py
│
├── integrations/
│   ├── github.py
│   ├── slack.py
│   └── webhooks.py
│
├── models/
│   ├── project.py
│   ├── test_case.py
│   ├── run.py
│   └── report.py
│
├── db/
│   └── database.py
│
└── cli/
    └── main.py              ← run | serve | worker commands
```
