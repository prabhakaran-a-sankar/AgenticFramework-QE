"""
QEAF MCP Server

Exposes all Quality Engineering Agentic Framework capabilities as MCP tools.
Any MCP-compatible AI client (Claude Desktop, VS Code Copilot, Cursor, Windsurf)
can use these tools directly from a conversation.

Usage:
    python mcp_server.py

Environment variables:
    LLM_PROVIDER       - openai | gemini | copilot  (default: openai)
    LLM_MODEL          - model name                  (default: gpt-4o)
    LLM_TEMPERATURE    - 0.0 to 1.0                  (default: 0.2)
    LLM_MAX_TOKENS     - max response tokens          (default: 8000)
    OPENAI_API_KEY     - required when provider=openai
    GEMINI_API_KEY     - required when provider=gemini
    GITHUB_TOKEN       - required when provider=copilot
"""

import os
import json
import shutil
from typing import Optional

from mcp.server.fastmcp import FastMCP

from quality_engineering_agentic_framework.llm.llm_factory import LLMFactory
from quality_engineering_agentic_framework.llm.copilot_llm import CopilotLLM
from quality_engineering_agentic_framework.agents.requirement_interpreter import TestCaseGenerationAgent
from quality_engineering_agentic_framework.agents.test_script_generator import TestScriptGenerator
from quality_engineering_agentic_framework.agents.test_data_generator import TestDataGenerator
from quality_engineering_agentic_framework.agents.api_test_case_creation import APITestCaseCreationAgent

mcp = FastMCP("QEAF")


def _build_llm():
    """
    Build an LLM instance from environment variables.

    For the MCP server, 'copilot' is handled directly via CopilotLLM
    (bypassing LLMFactory so it stays out of the UI dropdown).
    openai and gemini go through the shared LLMFactory as normal.
    """
    provider = os.environ.get("LLM_PROVIDER", "copilot").lower()

    config = {
        "provider": provider,
        "model": os.environ.get("LLM_MODEL", "gpt-4o"),
        "temperature": float(os.environ.get("LLM_TEMPERATURE", "0.2")),
        "max_tokens": int(os.environ.get("LLM_MAX_TOKENS", "8000")),
    }

    if provider == "copilot":
        github_token = os.environ.get("GITHUB_TOKEN", "")
        if not github_token:
            raise ValueError(
                "GITHUB_TOKEN is not set. "
                "Set it in the MCP server env config to your GitHub Personal Access Token."
            )
        config["api_key"] = github_token
        config["base_url"] = os.environ.get(
            "COPILOT_BASE_URL", "https://models.inference.ai.azure.com"
        )
        # OpenAI key passed only for RAG embeddings — Copilot still handles the LLM
        config["openai_api_key"] = os.environ.get("OPENAI_API_KEY", "")
        return CopilotLLM(config)

    elif provider == "openai":
        api_key = os.environ.get("OPENAI_API_KEY", "")
        if not api_key:
            raise ValueError("OPENAI_API_KEY is not set")
        config["api_key"] = api_key

    elif provider == "gemini":
        api_key = os.environ.get("GEMINI_API_KEY", "")
        if not api_key:
            raise ValueError("GEMINI_API_KEY is not set")
        config["api_key"] = api_key

    else:
        raise ValueError(
            f"Unsupported LLM_PROVIDER '{provider}'. Use: copilot, openai, gemini"
        )

    return LLMFactory.create_llm(config)


# ---------------------------------------------------------------------------
# Tool 1 — Generate Test Cases
# ---------------------------------------------------------------------------

@mcp.tool()
async def generate_test_cases(
    requirements: str,
    selected_documents: Optional[str] = None,
) -> str:
    """
    Generate comprehensive test cases from software requirements.

    Covers happy paths, negative flows, edge cases, and boundary conditions.
    Uses the Knowledge Hub (RAG) documents if available for project-specific context.

    Args:
        requirements: Feature description or requirement text to generate test cases for.
        selected_documents: Optional comma-separated filenames from the Knowledge Hub
                            to use as context (e.g. "spec.pdf,user_guide.docx").

    Returns:
        JSON with a list of structured test cases (title, preconditions, actions,
        expected_results, test_data, rag_ref).
    """
    llm = _build_llm()
    agent = TestCaseGenerationAgent(llm, {})

    doc_list = (
        [d.strip() for d in selected_documents.split(",") if d.strip()]
        if selected_documents
        else None
    )

    result = await agent.process(requirements, selected_documents=doc_list)
    return json.dumps(result, indent=2)


# ---------------------------------------------------------------------------
# Tool 2 — Generate Test Scripts
# ---------------------------------------------------------------------------

@mcp.tool()
async def generate_test_scripts(
    test_cases_json: str,
    language: str = "python",
    framework: str = "pytest",
    browser: str = "chrome",
    rendered_dom: Optional[str] = None,
) -> str:
    """
    Generate executable Selenium test automation scripts from test cases.

    Produces complete, runnable code including Page Object Model classes,
    imports, explicit waits, assertions, and error handling. No placeholders.

    Supported language + framework combinations:
      - python  : pytest | unittest | robot
      - java    : junit  | testng   | cucumber
      - javascript: jest | mocha    | cypress
      - c#      : nunit  | xunit    | mstest

    Args:
        test_cases_json: JSON string of test cases (output from generate_test_cases),
                         or a plain-text description of what to test.
        language:        Target programming language (default: python).
        framework:       Test framework for the chosen language (default: pytest).
        browser:         Browser driver to use — chrome | firefox | edge (default: chrome).
        rendered_dom:    Optional HTML source of the page under test. When provided,
                         locators are extracted directly from the DOM.

    Returns:
        Generated test scripts as code blocks, one file per block.
    """
    llm = _build_llm()
    agent = TestScriptGenerator(llm, {
        "language": language,
        "framework": framework,
        "browser": browser,
    })

    # Accept both raw JSON list and plain text
    try:
        test_cases = json.loads(test_cases_json)
        # Unwrap {"test_cases": [...]} envelope if present
        if isinstance(test_cases, dict) and "test_cases" in test_cases:
            test_cases = test_cases["test_cases"]
    except (json.JSONDecodeError, TypeError):
        # Plain text passed — wrap it so the agent can process it
        test_cases = [{"title": "Test", "actions": [test_cases_json], "expected_results": []}]

    result = await agent.process(test_cases, rendered_dom=rendered_dom)

    if isinstance(result, dict):
        # result is {filename: code} — format for readability
        parts = []
        for filename, code in result.items():
            parts.append(f"### {filename}\n```\n{code}\n```")
        return "\n\n".join(parts)

    return str(result)


# ---------------------------------------------------------------------------
# Tool 3 — Generate Test Data
# ---------------------------------------------------------------------------

@mcp.tool()
async def generate_test_data(
    test_cases: str,
    output_format: str = "json",
    data_variations: int = 5,
    include_edge_cases: bool = True,
) -> str:
    """
    Generate synthetic test data for test cases or test scripts.

    Creates realistic datasets including valid inputs, invalid inputs,
    boundary values, and edge cases.

    Args:
        test_cases:        Test cases or test script text to generate data for.
                           Can be the JSON output from generate_test_cases or plain text.
        output_format:     Format of the generated data — json | csv | sql (default: json).
        data_variations:   Number of data variations per test case (default: 5).
        include_edge_cases: Whether to include boundary/edge case data (default: true).

    Returns:
        Synthetic test data in the requested format.
    """
    llm = _build_llm()
    agent = TestDataGenerator(llm, {
        "output_format": output_format,
        "data_variations": data_variations,
        "include_edge_cases": include_edge_cases,
    })

    result = await agent.process(test_cases)
    return json.dumps(result, indent=2) if isinstance(result, (dict, list)) else str(result)


# ---------------------------------------------------------------------------
# Tool 4 — Generate API Test Cases
# ---------------------------------------------------------------------------

@mcp.tool()
async def generate_api_test_cases(
    base_url: str,
    endpoint: str,
    method: str,
    headers: Optional[str] = None,
    params: Optional[str] = None,
    body: Optional[str] = None,
    auth: Optional[str] = None,
) -> str:
    """
    Generate API test cases for a REST endpoint (like Postman Postbot).

    Produces 5-6 complete Java RestAssured + TestNG test methods covering:
    positive flows, negative flows, authentication failures, missing parameters,
    and invalid data scenarios.

    Args:
        base_url:  Base URL of the API (e.g. https://api.example.com).
        endpoint:  Endpoint path (e.g. /api/v1/users).
        method:    HTTP method — GET | POST | PUT | DELETE | PATCH.
        headers:   Optional JSON string of request headers
                   (e.g. '{"Content-Type": "application/json"}').
        params:    Optional JSON string of query parameters
                   (e.g. '{"page": 1, "limit": 10}').
        body:      Optional JSON string of the request body.
        auth:      Optional auth description (e.g. "Bearer token", "Basic auth", "API key").

    Returns:
        Complete Java test class with imports and multiple test methods.
    """
    llm = _build_llm()
    agent = APITestCaseCreationAgent(llm, {})

    api_details = {
        "base_url": base_url,
        "endpoint": endpoint,
        "method": method.upper(),
        "headers": json.loads(headers) if headers else {},
        "params":  json.loads(params)  if params  else {},
        "body":    json.loads(body)    if body    else {},
        "auth":    auth or "None",
    }

    result = await agent.process(api_details)
    return result if isinstance(result, str) else json.dumps(result, indent=2)


# ---------------------------------------------------------------------------
# Tool 5 — Add Requirement Document from any repo
# ---------------------------------------------------------------------------

@mcp.tool()
async def add_requirement_document(file_path: str) -> str:
    """
    Copy a requirement document from any location into the QEAF Knowledge Hub
    so it can be used as RAG context for test case generation.

    Call this first when your requirement file lives in another repo.
    After this, call generate_test_cases with the filename in selected_documents.

    Supported file types: PDF, TXT, DOCX

    Args:
        file_path: Absolute path to the requirement document in your repo
                   (e.g. /Users/you/my-project/docs/requirements.pdf)

    Returns:
        Confirmation message with the filename to use in selected_documents.
    """
    from quality_engineering_agentic_framework.utils.rag.rag_system import DATA_PATH, CACHE_PATH

    # Validate file exists
    if not os.path.isfile(file_path):
        return f"Error: File not found at '{file_path}'. Please provide an absolute path."

    # Validate file type
    ext = os.path.splitext(file_path)[1].lower()
    if ext not in (".pdf", ".txt", ".docx"):
        return f"Error: Unsupported file type '{ext}'. Supported types: .pdf, .txt, .docx"

    # Ensure RAG data directory exists
    os.makedirs(DATA_PATH, exist_ok=True)

    # Copy file into the RAG requirements folder
    filename = os.path.basename(file_path)
    dest_path = os.path.join(DATA_PATH, filename)
    shutil.copy2(file_path, dest_path)

    # Clear fingerprint cache so RAG re-indexes with the new document
    if os.path.exists(CACHE_PATH):
        os.remove(CACHE_PATH)

    return (
        f"Document '{filename}' added to the Knowledge Hub.\n"
        f"Now call generate_test_cases with selected_documents: \"{filename}\""
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    transport = os.environ.get("MCP_TRANSPORT", "stdio")
    if transport == "sse":
        import uvicorn
        host = os.environ.get("MCP_HOST", "0.0.0.0")
        port = int(os.environ.get("MCP_PORT", "8080"))
        print(f"Starting QEAF MCP server at http://{host}:{port}/sse")
        app = mcp.sse_app()
        uvicorn.run(app, host=host, port=port)
    else:
        mcp.run(transport="stdio")
