"""
Standalone Automation Agent

A standalone copy of the test automation agent, generalized to automate ANY
framework — UI (Selenium, Playwright, Cypress, WebdriverIO, ...) and API
(RestAssured, requests, supertest, RestSharp, ...).

Unlike the original TestScriptGenerator, this agent first *learns the existing
automation framework*: it detects the language and framework, learns the
directory structure, and extracts the existing classes and method signatures so
generated scripts FIT the project and REUSE what is already there instead of
duplicating helpers.

It can learn the framework from EITHER source, so it works with a local OR a
remote server:
  • disk — when project_path is on this server's filesystem (local server), or
  • a client-supplied file map (existing_files) — when the server is remote and
    the calling agent passes the relevant files in.

MCP-only agent: it is driven by the standalone_automation MCP tool and is not
referenced by the UI or the shared LLMFactory.
"""

import os
import re
from typing import Dict, Any, List, Optional

from quality_engineering_agentic_framework.agents.agent_interface import AgentInterface
from quality_engineering_agentic_framework.llm.llm_interface import LLMInterface
from quality_engineering_agentic_framework.utils.logger import get_logger

logger = get_logger(__name__)

# Directories that never contain hand-written framework code worth scanning.
_SKIP_DIRS = {
    ".git", "node_modules", "target", "build", "dist", "bin", "obj",
    "venv", ".venv", "__pycache__", ".idea", ".vscode", ".pytest_cache",
    "test-output", "allure-results", "reports", ".gradle", "out",
}

# Per-language: file extensions + lightweight signature extraction patterns.
_LANG_EXTS = {
    "java": [".java"],
    "python": [".py"],
    "javascript": [".js", ".ts", ".jsx", ".tsx"],
    "c#": [".cs"],
}

# Maximum files / chars we feed back so we never blow the context window.
_MAX_FILES_SCANNED = 250
_MAX_CONTEXT_CHARS = 18000

# Full-source context budgets (the most-relevant files, fed verbatim).
# Kept conservative: oversized sampling prompts make some hosts (e.g. the VS Code
# Copilot bridge) return "no choices".
_MAX_SOURCE_FILES = 3
_MAX_SOURCE_CHARS = 6000
_MAX_PER_SOURCE_CHARS = 2500
_MAX_EXAMPLE_CHARS = 3000

# Above this prompt size we skip the full prompt and start with the lean one,
# so small-context models don't choke ("no choices"). ~14k chars ≈ 3.5k tokens.
_FULL_PROMPT_CHAR_LIMIT = 14000

# Marker files → (language, build tool).
_MARKER_FILES = {
    "pom.xml": ("java", "maven"),
    "build.gradle": ("java", "gradle"),
    "build.gradle.kts": ("java", "gradle"),
    "package.json": ("javascript", "npm"),
    "requirements.txt": ("python", "pip"),
    "pyproject.toml": ("python", "pip"),
    "setup.py": ("python", "pip"),
    "pytest.ini": ("python", "pytest"),
}

# Dependency/keyword signal → canonical framework name.
_FRAMEWORK_SIGNALS = {
    "playwright": "playwright",
    "cypress": "cypress",
    "webdriverio": "webdriverio",
    "selenium": "selenium",
    "rest-assured": "restassured",
    "restassured": "restassured",
    "supertest": "supertest",
    "restsharp": "restsharp",
    "testng": "testng",
    "cucumber": "cucumber",
    "robotframework": "robot",
    "behave": "behave",
    "pytest": "pytest",
    "jest": "jest",
    "mocha": "mocha",
    "nunit": "nunit",
    "xunit": "xunit",
}


class StandaloneAutomationAgent(AgentInterface):
    """Generates automation scripts that fit an existing UI/API framework."""

    def __init__(self, llm: LLMInterface, config: Dict[str, Any]):
        super().__init__(llm, config)
        # All optional — auto-detected from the project when not given.
        self.language = self._norm(config.get("language"))
        self.framework = self._norm(config.get("framework"))
        self.automation_type = self._norm(config.get("automation_type")) or "ui"
        self.browser = self._norm(config.get("browser")) or "chrome"
        logger.info(
            f"Initialized StandaloneAutomationAgent "
            f"(type={self.automation_type}, language={self.language or 'auto'}, "
            f"framework={self.framework or 'auto'})"
        )

    @staticmethod
    def _norm(value: Optional[Any]) -> str:
        return str(value).lower().strip() if value else ""

    # ------------------------------------------------------------------
    # Framework discovery
    # ------------------------------------------------------------------

    @staticmethod
    def _read(path: str) -> str:
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                return f.read()
        except Exception:
            return ""

    def _detect_from_deps(self, deps_text: str, markers_lang: str = "",
                          markers_tool: str = "") -> Dict[str, Any]:
        """Detect framework set from accumulated dependency text + markers."""
        deps_lower = deps_text.lower()
        detected = [name for sig, name in _FRAMEWORK_SIGNALS.items() if sig in deps_lower]
        return {
            "language": self.language or markers_lang,
            "build_tool": markers_tool,
            "frameworks_detected": sorted(set(detected)),
            "framework": self.framework or (detected[0] if detected else ""),
        }

    @staticmethod
    def _infer_language_from_paths(paths) -> str:
        """Guess language from the most common known source extension."""
        counts: Dict[str, int] = {}
        for p in paths:
            for lang, exts in _LANG_EXTS.items():
                if any(p.endswith(e) for e in exts):
                    counts[lang] = counts.get(lang, 0) + 1
        return max(counts, key=counts.get) if counts else ""

    def _build_layout_and_sigs(self, pairs, language: str) -> Dict[str, Any]:
        """Build directory layout + reusable signatures from (relpath, content)
        pairs. Bounded by file/char caps. Shared by disk and in-memory paths."""
        exts = _LANG_EXTS.get(language, [])
        tree_dirs: set = set()
        reusable: List[str] = []
        sources: Dict[str, str] = {}
        files_scanned = 0
        total_chars = 0
        for rel_path, code in pairs:
            if exts and not any(rel_path.endswith(e) for e in exts):
                continue
            if files_scanned >= _MAX_FILES_SCANNED or total_chars >= _MAX_CONTEXT_CHARS:
                break
            files_scanned += 1
            sources[rel_path] = code  # retained for full-source selection
            tree_dirs.add(os.path.dirname(rel_path) or "(root)")
            sigs = self._extract_signatures(language, code)
            if sigs:
                block = f"{rel_path}:\n  " + "\n  ".join(sigs[:30])
                if total_chars + len(block) <= _MAX_CONTEXT_CHARS:
                    reusable.append(block)
                    total_chars += len(block)
        return {
            "directory_layout": sorted(tree_dirs),
            "existing_code": "\n\n".join(reusable),
            "files_scanned": files_scanned,
            "sources": sources,
        }

    def _detect_language_and_framework(self, project_path: str) -> Dict[str, Any]:
        """Detect language, build tool, and framework from project markers (disk)."""
        deps_text = ""
        markers_lang = ""
        markers_tool = ""
        for fname, (lang, tool) in _MARKER_FILES.items():
            fpath = os.path.join(project_path, fname)
            if os.path.isfile(fpath):
                if not markers_lang:
                    markers_lang, markers_tool = lang, tool
                deps_text += "\n" + self._read(fpath)

        if not markers_lang:  # C# project files live anywhere
            for root, dirs, files in os.walk(project_path):
                dirs[:] = [d for d in dirs if d not in _SKIP_DIRS]
                cs = [f for f in files if f.endswith(".csproj")]
                if cs:
                    markers_lang, markers_tool = "c#", "dotnet"
                    deps_text += "\n" + self._read(os.path.join(root, cs[0]))
                    break

        return self._detect_from_deps(deps_text, markers_lang, markers_tool)

    def _profile_from_filemap(self, files: Dict[str, str]) -> Dict[str, Any]:
        """Build the full framework profile from a CLIENT-SUPPLIED file map
        (path -> content). No disk access — used when the server is remote and
        the agent feeds the files in."""
        deps_text = ""
        markers_lang = ""
        markers_tool = ""
        for path, content in files.items():
            base = os.path.basename(path)
            if base in _MARKER_FILES:
                if not markers_lang:
                    markers_lang, markers_tool = _MARKER_FILES[base]
                deps_text += "\n" + content
            elif base.endswith(".csproj"):
                if not markers_lang:
                    markers_lang, markers_tool = "c#", "dotnet"
                deps_text += "\n" + content

        profile = self._detect_from_deps(deps_text, markers_lang, markers_tool)
        language = profile.get("language") or self._infer_language_from_paths(files.keys())
        profile["language"] = self.language or language
        profile.update(self._build_layout_and_sigs(files.items(), profile["language"]))
        logger.info(
            f"Built profile from {len(files)} client-supplied files "
            f"(language={profile['language']}, framework={profile.get('framework') or 'n/a'})"
        )
        return profile

    def _extract_signatures(self, language: str, code: str) -> List[str]:
        """Pull class names and method/function signatures from a source file."""
        sigs: List[str] = []
        if language == "python":
            sigs += [f"class {m}" for m in re.findall(r"^\s*class\s+(\w+[^\:\(]*)", code, re.M)]
            sigs += [f"def {m}(" for m in re.findall(r"^\s*def\s+(\w+\s*\([^)]*\))", code, re.M)]
        elif language in ("java", "c#"):
            sigs += [f"class {m}" for m in re.findall(r"\b(?:class|interface)\s+(\w+)", code)]
            sigs += re.findall(
                r"(?:public|protected|private)\s+[\w<>\[\],\s]+\s+(\w+\s*\([^)]*\))", code
            )
        elif language == "javascript":
            sigs += [f"class {m}" for m in re.findall(r"\bclass\s+(\w+)", code)]
            sigs += [f"function {m}(" for m in re.findall(r"function\s+(\w+\s*\([^)]*\))", code)]
            sigs += [f"{m}(" for m in re.findall(r"\b(\w+)\s*\([^)]*\)\s*\{", code)][:20]
        # de-dup, keep order
        seen, out = set(), []
        for s in sigs:
            s = s.strip()
            if s and s not in seen:
                seen.add(s)
                out.append(s)
        return out

    def _walk_pairs(self, project_path: str, exts: List[str]):
        """Yield (relpath, content) for files matching exts (reads only those)."""
        for root, dirs, files in os.walk(project_path):
            dirs[:] = [d for d in dirs if d not in _SKIP_DIRS]
            for fname in files:
                if exts and not any(fname.endswith(e) for e in exts):
                    continue
                fpath = os.path.join(root, fname)
                yield os.path.relpath(fpath, project_path), self._read(fpath)

    def _scan_framework(self, project_path: str, language: str) -> Dict[str, Any]:
        """Walk the project on disk and collect structure + reusable signatures."""
        exts = _LANG_EXTS.get(language, [])
        if not exts:
            return {"directory_layout": [], "existing_code": "", "files_scanned": 0}
        result = self._build_layout_and_sigs(self._walk_pairs(project_path, exts), language)
        logger.info(
            f"Scanned framework at {project_path}: {result['files_scanned']} files, "
            f"{len(result['existing_code'].split(chr(10)+chr(10))) if result['existing_code'] else 0} "
            f"files with reusable code"
        )
        return result

    # ------------------------------------------------------------------
    # Generation
    # ------------------------------------------------------------------

    def _build_input_text(
        self,
        test_cases: Any,
        rendered_dom: Optional[str],
        api_details: Optional[Dict[str, Any]],
        app_url: Optional[str] = None,
    ) -> str:
        parts = []
        if app_url:
            parts.append(f"Application URL under test: {app_url}")
        if isinstance(test_cases, list):
            for i, tc in enumerate(test_cases, 1):
                if isinstance(tc, dict):
                    parts.append(f"Test Case {i}: {tc.get('title', 'Untitled')}")
                    if tc.get("description"):
                        parts.append(f"  Description: {tc['description']}")
                    for a in tc.get("actions", []):
                        parts.append(f"  - {a if isinstance(a, str) else a.get('action', a)}")
                    for r in tc.get("expected_results", []):
                        parts.append(f"  Expected: {r}")
                else:
                    parts.append(f"- {tc}")
        elif test_cases:
            parts.append(str(test_cases))

        if api_details:
            parts.append("\nAPI under test:")
            for k, v in api_details.items():
                parts.append(f"  {k}: {v}")
        if rendered_dom:
            parts.append(f"\nRendered DOM of the page under test:\n{rendered_dom[:6000]}")
        return "\n".join(parts) if parts else "Generate automation scripts for the project."

    @staticmethod
    def _detect_module_system(language: str, file_map: Dict[str, str],
                              project_path: Optional[str] = None) -> str:
        """State the import/export convention so generated code matches it."""
        if language == "javascript":
            pkg = next((c for p, c in file_map.items()
                        if os.path.basename(p) == "package.json"), "")
            if not pkg and project_path:
                pp = os.path.join(project_path, "package.json")
                if os.path.isfile(pp):
                    pkg = StandaloneAutomationAgent._read(pp)
            if '"type"' in pkg and '"module"' in pkg:
                return ("ES Modules (ESM) — use `import ... from` / `export`; "
                        "package.json declares \"type\": \"module\".")
            sample = "\n".join(list(file_map.values())[:6])[:6000]
            if "module.exports" in sample or "require(" in sample:
                return ("CommonJS — use `const X = require(...)` and `module.exports`; "
                        "match the existing files exactly.")
            if re.search(r"^\s*import\s", sample, re.M) or "export " in sample:
                return "ES Modules (ESM) — use `import`/`export`; match the existing files exactly."
            return "Match the exact import/export style of the provided files."
        if language == "python":
            return "Python — use `from <package>.<module> import <Name>`; match existing import paths exactly."
        if language == "java":
            return "Java — match existing package declarations and import statements."
        if language == "c#":
            return "C# — match existing `using`/namespace conventions."
        return "Match the import/export conventions shown in the provided files."

    def _select_relevant_sources(self, file_map: Dict[str, str], instructions_text: str):
        """Pick the few most-relevant existing files; return [(path, full_source)]."""
        kws = {w.lower() for w in re.findall(r"[A-Za-z]{4,}", instructions_text or "")}
        type_hints = ("page", "fixture", "base", "util", "helper", "client",
                      "api", "locator", "selector", "conftest", "common")
        scored = []
        for path, content in file_map.items():
            base = os.path.basename(path).lower()
            if base == "package.json" or not content or not content.strip():
                continue
            name_tokens = set(re.findall(r"[a-z]+", base))
            score = len(kws & name_tokens) * 3 + sum(1 for h in type_hints if h in base)
            if score > 0:
                scored.append((score, len(content), path))
        scored.sort(key=lambda t: (-t[0], t[1]))  # best score, then smaller files
        chosen, used = [], 0
        for _, _, path in scored:
            snippet = file_map[path][:_MAX_PER_SOURCE_CHARS]
            if used + len(snippet) > _MAX_SOURCE_CHARS:
                continue
            chosen.append((path, snippet))
            used += len(snippet)
            if len(chosen) >= _MAX_SOURCE_FILES:
                break
        return chosen

    @staticmethod
    def _pick_example_test(file_map: Dict[str, str], exclude):
        """Return one existing test/spec file as a style exemplar, or None."""
        for path, content in file_map.items():
            base = os.path.basename(path).lower()
            if path in exclude or not content or not content.strip():
                continue
            if "test" in base or "spec" in base:
                return path, content[:_MAX_EXAMPLE_CHARS]
        return None

    @staticmethod
    def _analyze_test_style(example_code: str) -> List[str]:
        """Derive a concrete 'style contract' from a real existing test so the
        generated test matches its architecture (fixtures, raw page vs page-object,
        locator source, data source) instead of inventing a different pattern."""
        notes: List[str] = []
        if not example_code:
            return notes
        m = re.search(r"\btest(?:\.\w+)?\s*\(\s*[^,]+,\s*async\s*\(\s*\{([^}]*)\}", example_code)
        if m:
            params = ", ".join(p.strip() for p in m.group(1).split(",") if p.strip())
            notes.append(f"Use the EXACT test signature `async ({{ {params} }}) => …` "
                         f"— the same fixtures, nothing else.")
        if "describe.serial" in example_code:
            notes.append("Group tests in `test.describe.serial(...)` like the example.")
        elif re.search(r"\bdescribe\s*\(", example_code):
            notes.append("Group tests in `test.describe(...)` like the example.")
        if re.search(r"\bpage\.(goto|fill|click|locator|waitFor)\b", example_code):
            notes.append("Call Playwright `page.*` actions DIRECTLY (goto/fill/click/locator). "
                         "Do NOT introduce page-object wrapper methods or a custom page fixture.")
        if re.search(r"page\.(fill|click|locator)\(\s*[A-Za-z_]\w*\b", example_code):
            notes.append("Selectors are imported/module-level CONSTANTS (e.g. `username`, "
                         "`loginButton`) — reuse those constants, not inline strings or getters.")
        if "testData" in example_code:
            notes.append("Test data comes from the existing `testData` object "
                         "(e.g. `testData.standard_user`) — reuse it.")
        if "newContext(" in example_code:
            notes.append("Create context/page the same way the example does "
                         "(e.g. `browser.newContext()` then `context.newPage()`).")
        return notes

    def _best_practice_standards(self, language: str, framework: str, atype: str) -> List[str]:
        """Standards to apply for a NEW project that has nothing to learn from."""
        s = [
            "Use a clear layout: tests/ (specs), pages/ or clients/ (reusable code), "
            "fixtures/ or utils/ (helpers), data/ (test data), config/ (env/base URL).",
            "Descriptive test names; consistent casing for the language "
            "(PascalCase classes, camelCase JS methods / snake_case Python).",
            "Each test INDEPENDENT and idempotent — sets up its own state in setup/fixtures; "
            "no reliance on test order.",
            "Externalize config & data: base URL, credentials, and test data come from "
            "config/env/data files — NEVER hardcode them in tests.",
            "Meaningful assertions on observable outcomes; clear failure messages.",
            "Proper error handling; fully runnable code with no placeholders/TODOs.",
        ]
        if atype in ("ui", "both"):
            s += [
                "UI: use the Page Object Model — encapsulate selectors + actions in page "
                "classes; keep selectors centralized (no scattered magic strings).",
                "UI: use explicit/auto waits for elements (visible/clickable) — never hard sleeps.",
                "UI: a fresh browser context per test; establish auth in setup "
                "(reuse a login helper or a saved session/storage state).",
            ]
        if atype in ("api", "both"):
            s += [
                "API: a reusable request/client layer separate from the assertions.",
                "API: validate status code, response body (and schema), and key headers.",
                "API: cover positive, negative, auth-failure, and boundary cases; "
                "data-drive variations.",
            ]
        fw = (framework or "").lower()
        if fw == "playwright":
            s.append("Playwright: use fixtures + `expect()` web-first assertions and "
                     "auto-waiting locators; storageState for auth where helpful.")
        elif fw in ("pytest", "selenium") and language == "python":
            s.append("pytest: use fixtures/conftest for setup and `@pytest.mark.parametrize` "
                     "for data-driven tests.")
        elif fw in ("restassured", "testng"):
            s.append("RestAssured/TestNG: given/when/then structure, a base test class, "
                     "and @DataProvider for variations.")
        return s

    async def process(
        self,
        test_cases: Any,
        project_path: Optional[str] = None,
        existing_files: Optional[Dict[str, str]] = None,
        rendered_dom: Optional[str] = None,
        api_details: Optional[Dict[str, Any]] = None,
        app_url: Optional[str] = None,
    ) -> Dict[str, str]:
        profile = {"language": self.language, "framework": self.framework,
                   "frameworks_detected": [], "directory_layout": [], "existing_code": ""}

        # Prefer client-supplied files (works with a remote server); otherwise
        # read from disk when the project is local to this server.
        file_map: Dict[str, str] = {}
        if existing_files:
            profile.update(self._profile_from_filemap(existing_files))
            file_map = existing_files
        elif project_path and os.path.isdir(project_path):
            detected = self._detect_language_and_framework(project_path)
            profile.update(detected)
            scan = self._scan_framework(project_path, profile.get("language", ""))
            profile.update(scan)
            file_map = scan.get("sources", {})
        elif project_path:
            logger.warning(f"project_path '{project_path}' is not a directory; skipping scan")

        language = profile.get("language") or "python"
        framework = profile.get("framework") or ("the project's framework")
        input_text = self._build_input_text(test_cases, rendered_dom, api_details, app_url)

        # Full source of the most-relevant files (kills "method doesn't exist" /
        # wrong import-export), a real test as a style exemplar, and the module system.
        relevant = self._select_relevant_sources(file_map, input_text)
        example = self._pick_example_test(file_map, {p for p, _ in relevant})
        module_note = self._detect_module_system(language, file_map, project_path)

        if not example:
            logger.warning("No example test in provided files — STYLE fidelity reduced; "
                           "pass an existing test (and its locator/data modules) for best results.")
        if not relevant:
            logger.warning("No relevant source files provided — REUSE fidelity reduced; "
                           "pass the page objects/helpers the test should reuse.")

        sources_block = ""
        if relevant:
            blocks = [f"--- {p} ---\n{src}" for p, src in relevant]
            sources_block = (
                "\nRELEVANT EXISTING FILES — FULL SOURCE "
                "(you may ONLY call methods/classes that appear here):\n"
                + "\n\n".join(blocks) + "\n"
            )

        style_notes = self._analyze_test_style(example[1]) if example else []
        example_block = ""
        if example:
            contract = ""
            if style_notes:
                contract = ("\nSTYLE CONTRACT — your generated test MUST follow ALL of these "
                            "(derived from the example):\n"
                            + "\n".join(f"  - {n}" for n in style_notes) + "\n")
            example_block = (
                "\nEXAMPLE EXISTING TEST (replicate its architecture EXACTLY — same fixtures, "
                "same page/locator/data approach, same assertions):\n"
                f"--- {example[0]} ---\n{example[1]}\n{contract}"
            )

        # Broad signature index for the rest of the codebase (trimmed when we
        # already have full sources, to keep the prompt lean).
        sig_index = profile.get("existing_code", "")
        if relevant and len(sig_index) > 3000:
            sig_index = sig_index[:3000] + "\n…(truncated)"
        index_block = (
            f"\nOTHER FILES (signatures only, for reference):\n{sig_index}\n"
            if sig_index else
            ("" if relevant else "\nNo existing framework code was found to reuse.\n")
        )

        layout_block = (
            f"\nEXISTING DIRECTORY LAYOUT (place new files following this structure):\n"
            + "\n".join(f"  - {d}" for d in profile.get("directory_layout", []))
            if profile.get("directory_layout")
            else ""
        )

        # Adaptive standards: LEARN from the host's existing standards when there is
        # something to learn from; otherwise (new/greenfield project) GENERATE with
        # professional coding & testing standards.
        has_existing = bool(relevant or example or profile.get("existing_code"))
        if has_existing:
            standards_block = (
                "\nCODING STANDARDS — LEARN FROM AND STRICTLY FOLLOW the existing project's "
                "conventions shown above (structure, naming, fixtures, locator/data approach, "
                "imports, assertions). Match them exactly; do NOT impose a different style.\n"
            )
            standards_intro = "existing"
        else:
            bullets = self._best_practice_standards(language, framework, self.automation_type)
            standards_block = (
                "\nNEW PROJECT — there are NO existing standards to learn from. Generate a clean "
                "foundation that follows these professional coding & testing standards:\n"
                + "\n".join(f"  - {b}" for b in bullets) + "\n"
            )
            standards_intro = "new"
        logger.info(f"  standards mode: {'follow existing' if has_existing else 'apply best-practice (greenfield)'}")

        system_message = (
            "You are a senior test automation engineer. You work in TWO modes: "
            "(A) EXTENDING an existing framework — then LEARN and STRICTLY FOLLOW its existing "
            "coding & testing standards (structure, naming, fixtures, locator/data approach, "
            "imports, assertions), call ONLY methods/classes that appear in the provided files, "
            "and NEVER invent methods or impose a different style; "
            "(B) a NEW project with nothing to learn from — then GENERATE a clean foundation that "
            "applies professional coding & testing standards (clear structure, POM for UI, "
            "reusable client layer for API, externalized config/data, explicit waits, independent "
            "tests, meaningful assertions). Always produce fully executable code — no placeholders."
        )

        prompt = f"""Generate {self.automation_type.upper()} automation scripts ({'EXTEND the existing project' if has_existing else 'NEW project foundation'}).

Detected language: {language}
Detected framework: {framework}
Other frameworks present: {', '.join(profile.get('frameworks_detected', [])) or 'none'}
Automation type: {self.automation_type} (ui | api | both)
Browser (if UI): {self.browser}
Module/import system: {module_note}
{standards_block}{layout_block}
{sources_block}{example_block}{index_block}
WHAT TO AUTOMATE:
{input_text}

GUIDELINES:
{'- Call ONLY methods/classes/properties that appear in the RELEVANT EXISTING FILES above. Do NOT invent methods on existing classes. If something needed is genuinely missing, add a minimal new helper rather than guessing a method name.' if has_existing else '- Build reusable building blocks (page objects / API client, fixtures, config, data) per the standards above.'}
- Match the EXACT import/export style shown ({module_note}).
{'- Replicate the EXAMPLE TEST architecture EXACTLY and follow every STYLE CONTRACT rule. Do NOT introduce a page-object pattern, custom fixtures (e.g. `{ loginPage }`), or wrapper methods (e.g. `loginPage.getTitle()`) unless the example uses them.' if example else '- Establish a consistent, idiomatic structure since there is no example to match.'}
- {'Reuse existing page objects/fixtures/utilities; only add what is truly missing.' if has_existing else 'Externalize selectors, config, and test data — do not hardcode.'}
- {'Follow the existing directory layout when choosing file paths.' if profile.get('directory_layout') else 'Use a clear, conventional directory layout.'}
- Include imports, waits/assertions (UI) or request/response validation (API), error handling.
- Return EACH file in its own code block tagged with language and the full relative path:
```{language}:relative/path/to/File.ext
// full file content
```
"""

        # Progressive, size-aware generation ladder so it works even on small
        # models (small context/output, prone to "no choices" on big requests):
        #   full  → lean  → minimal-single-file.
        # If the full prompt is already large, skip it and start lean.
        lean_system = (
            "You are a senior test automation engineer. Match the existing style, "
            "reuse existing methods, never invent methods, no placeholders."
        )
        # Compact signatures of the relevant files — cheap way to keep "reuse the
        # real method names" fidelity even in the small prompts (avoids inventing).
        rel_sigs = []
        for p, src in relevant:
            s = self._extract_signatures(language, src)
            if s:
                rel_sigs.append(f"{os.path.basename(p)}: " + ", ".join(s[:12]))
        sig_hint = "\n".join(rel_sigs)[:1500]

        lean_prompt = self._build_lean_prompt(
            language, framework, has_existing, module_note, style_notes, example, input_text, sig_hint)
        minimal_prompt = self._build_minimal_prompt(
            language, style_notes, example, input_text, sig_hint)

        attempts = []
        if len(prompt) <= _FULL_PROMPT_CHAR_LIMIT:
            attempts.append(("full", prompt, system_message, 4000))
        else:
            logger.info(f"  full prompt is large ({len(prompt)} chars) → starting lean for small-model safety.")
        attempts.append(("lean", lean_prompt, lean_system, 3000))
        attempts.append(("minimal", minimal_prompt, lean_system, 2000))

        response = ""
        for label, pr, sm, mt in attempts:
            logger.info(f"  generation attempt: {label} (prompt {len(pr)} chars, max_tokens {mt})")
            try:
                response = await self.llm.generate(
                    prompt=pr, system_message=sm, temperature=0.3, max_tokens=mt)
            except Exception as e:
                logger.warning(f"  {label} attempt failed: {e}")
                response = ""
            if response and response.strip():
                logger.info(f"  generation succeeded on '{label}' attempt.")
                break

        if not response or not response.strip():
            return {"error.txt": "Model returned no content (host sampling produced no choices) "
                                 "even after lean retries. Try a more capable Copilot model."}
        files = self._parse_files_from_response(response)
        if not files:
            return {"generated_output.txt": response}
        return files

    def _build_lean_prompt(self, language, framework, has_existing, module_note,
                           style_notes, example, input_text, sig_hint="") -> str:
        """A smaller prompt for retry when the host rejects a large request."""
        parts = [
            f"Generate {self.automation_type.upper()} automation for a "
            f"{'existing' if has_existing else 'new'} {language}/{framework} project.",
            f"Module/import system: {module_note}",
        ]
        if sig_hint:
            parts.append("REUSE ONLY THESE existing classes/methods (do NOT invent others):\n"
                         + sig_hint)
        if style_notes:
            parts.append("STYLE CONTRACT (match exactly):\n"
                         + "\n".join(f"  - {n}" for n in style_notes))
        if example:
            parts.append(f"EXAMPLE TEST (match this style):\n{example[1][:1500]}")
        parts.append(f"WHAT TO AUTOMATE:\n{input_text}")
        parts.append(
            "Rules: match the existing style; reuse existing methods; do NOT invent methods; "
            "no placeholders. Return each file as a code block tagged with its path:\n"
            f"```{language}:relative/path/File.ext\n<full file>\n```"
        )
        return "\n\n".join(parts)

    def _build_minimal_prompt(self, language, style_notes, example, input_text, sig_hint="") -> str:
        """Smallest possible prompt — ONE focused output, for the weakest models."""
        parts = [f"Write the {self.automation_type.upper()} test file for:\n{input_text}"]
        if sig_hint:
            parts.append("Reuse ONLY these existing methods (don't invent):\n" + sig_hint[:700])
        if style_notes:
            parts.append("Match this style:\n" + "\n".join(f"- {n}" for n in style_notes[:4]))
        if example:
            parts.append(f"Like this existing test:\n{example[1][:900]}")
        parts.append(
            "Generate ONLY the test file (reuse existing helpers by name; do not "
            f"regenerate page objects). Return it as:\n```{language}:tests/your_test.ext\n<file>\n```"
        )
        return "\n\n".join(parts)

    # Config files most likely to hold a base URL / auth scheme.
    _CONFIG_NAMES = {
        ".env", ".env.test", ".env.local", "config.yaml", "config.yml",
        "application.properties", "application.yml", "application.yaml",
        "cypress.config.js", "cypress.config.ts", "cypress.json",
        "playwright.config.js", "playwright.config.ts", "wdio.conf.js",
        "pytest.ini", "tox.ini", "testng.xml", "pom.xml",
        "config.py", "settings.py", "constants.py", "package.json",
    }
    # also read source files whose name hints at config/constants
    _CONFIG_NAME_HINT = re.compile(r"(?i)(config|constant|setting|base[_-]?url|env)")

    _URL_RE = re.compile(
        r"""(?ix)
        (base[\s_.]*url | base[\s_.]*uri | baseuri | app[\s_.]*url | server[\s_.]*url)
        \s*[:=]\s*["']?(https?://[^\s"'<>,;)]+)
        """
    )

    @classmethod
    def discover_config(cls, project_path: Optional[str] = None,
                        files: Optional[Dict[str, str]] = None,
                        config_text: str = "") -> Dict[str, str]:
        """
        Look for a base URL and auth scheme ALREADY defined in the project's
        config, so we don't have to ask the user. Works from a client-supplied
        file map / config_text (remote server) OR from disk (local server).
        Returns {"base_url": "...", "auth": "..."} — empty if nothing found
        (e.g. a brand-new framework built from scratch).
        """
        found = {"base_url": "", "auth": ""}
        texts: List[str] = []
        if config_text:
            texts.append(config_text)

        def consider(name: str, content: str):
            if name in cls._CONFIG_NAMES or cls._CONFIG_NAME_HINT.search(name):
                texts.append(content)
                if not found["base_url"]:
                    m = cls._URL_RE.search(content)
                    if m:
                        found["base_url"] = m.group(2).rstrip("/")
                        logger.info(f"Discovered base URL from {name}: {found['base_url']}")

        if files:
            for path, content in files.items():
                consider(os.path.basename(path), content[:20000])
        elif project_path and os.path.isdir(project_path):
            files_read = 0
            for root, dirs, fs in os.walk(project_path):
                dirs[:] = [d for d in dirs if d not in _SKIP_DIRS]
                for fname in fs:
                    if files_read >= 60:
                        break
                    if fname in cls._CONFIG_NAMES or cls._CONFIG_NAME_HINT.search(fname):
                        content = cls._read(os.path.join(root, fname))[:20000]
                        files_read += 1
                        consider(fname, content)

        blob = "\n".join(texts).lower()
        if re.search(r"x-api-key|api[_-]?key", blob):
            found["auth"] = "apikey"
        elif "bearer" in blob or "oauth" in blob:
            found["auth"] = "bearer"
        elif re.search(r"basic[\s_-]*auth", blob):
            found["auth"] = "basic"
        elif "authorization" in blob or "token" in blob:
            found["auth"] = "bearer"
        if found["auth"]:
            logger.info(f"Discovered auth scheme from project config: {found['auth']}")
        return found

    @staticmethod
    def write_files(files: Dict[str, str], project_path: str) -> List[Dict[str, str]]:
        """
        Write generated files into the project at their relative paths.

        Path-safe: any file that would resolve outside project_path (e.g. via
        '../') is refused. Returns a per-file report with status:
        created | updated | refused | error.
        """
        report: List[Dict[str, str]] = []
        base = os.path.normpath(os.path.abspath(project_path))
        for rel_path, code in files.items():
            full = os.path.normpath(os.path.join(base, rel_path))
            if full != base and not full.startswith(base + os.sep):
                report.append({"file": rel_path, "status": "refused",
                               "detail": "path escapes project directory"})
                logger.warning(f"Refused to write outside project: {rel_path}")
                continue
            try:
                existed = os.path.exists(full)
                os.makedirs(os.path.dirname(full), exist_ok=True)
                with open(full, "w", encoding="utf-8") as f:
                    f.write(code)
                report.append({"file": rel_path,
                               "status": "updated" if existed else "created",
                               "detail": full})
            except Exception as e:
                report.append({"file": rel_path, "status": "error", "detail": str(e)})
                logger.error(f"Failed to write {rel_path}: {e}")
        return report

    async def _heal_one(self, filename: str, code: str, error: str) -> Optional[str]:
        """Ask the model to fix a single file that failed a static check."""
        ext = os.path.splitext(filename)[1].lstrip(".") or "txt"
        prompt = (
            f"This {ext} file failed a static (load-time) check and must be fixed.\n"
            f"Error: {error}\n\n"
            f"File `{filename}`:\n```\n{code}\n```\n\n"
            f"Return ONLY the corrected, complete file as a single code block tagged "
            f"with its path, no explanation:\n```{ext}:{filename}\n<full corrected file>\n```"
        )
        try:
            resp = await self.llm.generate(
                prompt=prompt,
                system_message=(
                    "You fix code so it parses/compiles cleanly. Preserve the intent and "
                    "structure; change only what's needed to make it load. Return the full file."
                ),
                temperature=0.1,
                max_tokens=4000,
            )
            fixed = self._parse_files_from_response(resp)
            if filename in fixed:
                return fixed[filename]
            return next(iter(fixed.values()), None)
        except Exception as e:
            logger.error(f"Heal of {filename} failed: {e}")
            return None

    async def heal_static(self, files: Dict[str, str], max_attempts: int = 2):
        """
        Phase 1 self-heal: validate; for any file with a hard load-time failure,
        ask the model to fix it; re-validate; repeat up to max_attempts.

        Cheap by design: makes NO extra model calls when the code is already
        clean. Returns (files, validation_report, heal_log).
        """
        from quality_engineering_agentic_framework.utils.code_validation import (
            validate_and_format, failure_reason,
        )
        log: List[str] = []
        files, report = validate_and_format(files)

        for attempt in range(1, max_attempts + 1):
            broken = [e for e in report if not e.get("ok", True)]
            if not broken:
                log.append(f"attempt {attempt}: all files pass static checks ✅")
                return files, report, log

            for entry in broken:
                fname = entry["file"]
                reason = failure_reason(entry)
                log.append(f"attempt {attempt}: `{fname}` failed — {reason} → healing")
                fixed = await self._heal_one(fname, files[fname], reason)
                if fixed:
                    files[fname] = fixed

            files, report = validate_and_format(files)

        still = [e["file"] for e in report if not e.get("ok", True)]
        if still:
            log.append(f"still failing after {max_attempts} attempts: {still}")
        else:
            log.append("all files pass static checks after healing ✅")
        return files, report, log

    def _parse_files_from_response(self, response: str) -> Dict[str, str]:
        files: Dict[str, str] = {}
        if not response:
            return files
        matches = re.findall(r"```(?:[\w#+]+):([^\n]+)\n([\s\S]*?)```", response)
        for filename, code in matches:
            files[filename.strip()] = code.strip()
        return files

    def get_name(self) -> str:
        return "standalone_automation_agent"

    def get_description(self) -> str:
        return (
            "Reads an existing UI/API automation framework, reuses its methods and "
            "structure, and generates fitting automation scripts for any framework."
        )
