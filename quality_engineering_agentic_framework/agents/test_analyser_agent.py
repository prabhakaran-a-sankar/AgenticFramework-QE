"""
Test Analyser Agent

Scans an existing test project, understands each test's intent, and rewrites
it in a chosen output format — BDD (Gherkin), plain test cases, or step-by-step.
The result is exported as a styled Excel workbook (.xlsx).

Works like standalone_automation but READ-ONLY: it never writes to the project
under test.  Its sole output is the .xlsx artefact.

Supported output formats
------------------------
  bdd         — Feature / Scenario / Given / When / Then / Tags
  plain       — Test ID / Title / Preconditions / Steps / Expected Result
  step_by_step— Step # / Action / Expected Result  (one row per step)

MCP-only agent — not referenced by the UI or LLMFactory.
"""

import base64
import io
import json
import os
import re
from typing import Any, Dict, List, Optional

from quality_engineering_agentic_framework.agents.agent_interface import AgentInterface
from quality_engineering_agentic_framework.llm.llm_interface import LLMInterface
from quality_engineering_agentic_framework.utils.logger import get_logger

logger = get_logger(__name__)

# ── Directories to skip while walking the project ────────────────────────────
_SKIP_DIRS = {
    ".git", "node_modules", "target", "build", "dist", "bin", "obj",
    "venv", ".venv", "__pycache__", ".idea", ".vscode", ".pytest_cache",
    "test-output", "allure-results", "reports", ".gradle", "out",
}

# ── Project-marker → language ─────────────────────────────────────────────────
_MARKER_TO_LANG: Dict[str, str] = {
    "pom.xml":          "java",
    "build.gradle":     "java",
    "build.gradle.kts": "java",
    "package.json":     "javascript",
    "requirements.txt": "python",
    "pyproject.toml":   "python",
    "setup.py":         "python",
    "pytest.ini":       "python",
}

# ── Per-language: extensions + test/class regexes ─────────────────────────────
_LANG_CFG: Dict[str, Dict] = {
    "python": {
        "exts":      [".py"],
        "file_re":   re.compile(r"(test_.*|.*_test)\.py$", re.I),
        "method_re": re.compile(r"^\s*(?:async\s+)?def\s+(test\w*)\s*\([^)]*\)", re.M),
        "class_re":  re.compile(r"^\s*class\s+(Test\w+)", re.M),
    },
    "java": {
        "exts":      [".java"],
        "file_re":   re.compile(r".*Test.*\.java$|.*IT\.java$", re.I),
        "method_re": re.compile(r"@Test[^;]*?\s+(?:public\s+)?(?:void\s+)?(\w+)\s*\(", re.M | re.S),
        "class_re":  re.compile(r"(?:public\s+)?class\s+(\w+)", re.M),
    },
    "javascript": {
        "exts":      [".js", ".ts", ".jsx", ".tsx"],
        "file_re":   re.compile(r".*\.(spec|test)\.(js|ts|jsx|tsx)$", re.I),
        "method_re": re.compile(r"(?:it|test)\s*\(\s*['\"`]([^'\"` \n]+)['\"`]", re.M),
        "class_re":  re.compile(r"describe\s*\(\s*['\"`]([^'\"` \n]+)['\"`]", re.M),
    },
    "c#": {
        "exts":      [".cs"],
        "file_re":   re.compile(r".*Tests?.*\.cs$", re.I),
        "method_re": re.compile(
            r"\[(?:Test|Fact|Theory|TestMethod)[^\]]*\]\s+(?:public\s+)?(?:\w+\s+)?(\w+)\s*\(", re.M
        ),
        "class_re":  re.compile(r"(?:public\s+)?class\s+(\w+)", re.M),
    },
}

_MAX_FILES           = 120   # total test files to scan
_MAX_BODY_CHARS      = 600   # chars of method body sent to LLM per test
_BATCH_SIZE          = 15    # tests per LLM call
FILE_ELICIT_THRESHOLD = 20   # ask user to pick files when more than this many are found

# ── Output-format column definitions ─────────────────────────────────────────
_FORMAT_COLUMNS: Dict[str, List[tuple]] = {
    "bdd": [
        ("Feature",     24),
        ("Scenario",    44),
        ("Given",       46),
        ("When",        46),
        ("Then",        46),
        ("Tags",        20),
        ("Source File", 40),
        ("Line",         6),
    ],
    "plain": [
        ("Test ID",          10),
        ("Title",            44),
        ("Preconditions",    40),
        ("Steps",            50),
        ("Expected Result",  50),
        ("Priority",         12),
        ("Source File",      40),
        ("Line",              6),
    ],
    "step_by_step": [
        ("Test ID",          10),
        ("Test Title",       40),
        ("Step #",            8),
        ("Action",           50),
        ("Expected Result",  50),
        ("Source File",      40),
        ("Line",              6),
    ],
}

SUPPORTED_FORMATS = list(_FORMAT_COLUMNS.keys())


class TestAnalyserAgent(AgentInterface):
    """
    Reads an existing test project and exports structured test cases to Excel.

    Accepts input either from disk (project_path) or from a caller-supplied
    file map {path: content} — the same LOCAL / REMOTE pattern used by the
    standalone_automation agent.
    """

    def __init__(self, llm: LLMInterface, config: Dict[str, Any]):
        super().__init__(llm, config)
        self.language      = self._norm(config.get("language"))
        self.output_format = self._norm(config.get("output_format")) or "bdd"
        if self.output_format not in SUPPORTED_FORMATS:
            logger.warning(
                f"Unknown output_format '{self.output_format}'; defaulting to 'bdd'."
            )
            self.output_format = "bdd"
        logger.info(
            f"TestAnalyserAgent init (language={self.language or 'auto'}, "
            f"format={self.output_format})"
        )

    # ── small helpers ─────────────────────────────────────────────────────────

    @staticmethod
    def _norm(value: Any) -> str:
        return str(value).lower().strip() if value else ""

    @staticmethod
    def _read(path: str) -> str:
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as fh:
                return fh.read()
        except Exception:
            return ""

    # ── language detection ────────────────────────────────────────────────────

    def _detect_language(
        self,
        project_path: Optional[str],
        file_map: Optional[Dict[str, str]],
    ) -> str:
        if self.language:
            return self.language

        if file_map:
            for path in file_map:
                base = os.path.basename(path)
                if base in _MARKER_TO_LANG:
                    return _MARKER_TO_LANG[base]
                if base.endswith(".csproj"):
                    return "c#"
            counts: Dict[str, int] = {
                lang: sum(1 for p in file_map if any(p.endswith(e) for e in cfg["exts"]))
                for lang, cfg in _LANG_CFG.items()
            }
            return max(counts, key=counts.get) if any(counts.values()) else "python"

        if project_path:
            for marker, lang in _MARKER_TO_LANG.items():
                if os.path.isfile(os.path.join(project_path, marker)):
                    return lang
            for root, dirs, files in os.walk(project_path):
                dirs[:] = [d for d in dirs if d not in _SKIP_DIRS]
                if any(f.endswith(".csproj") for f in files):
                    return "c#"
                break  # only top level for markers

        return "python"

    # ── quick scan (no LLM — used for elicitation) ───────────────────────────

    @classmethod
    def quick_scan(cls, project_path: str, language: str) -> List[Dict[str, Any]]:
        """
        Fast directory walk — returns [{path, abs_path, test_count}] for every
        test file found.  No LLM calls; used by the MCP tool to build the
        elicitation prompt when the project is large.
        """
        cfg      = _LANG_CFG.get(language, {})
        file_re  = cfg.get("file_re")
        exts     = cfg.get("exts", [])
        method_re = cfg.get("method_re")

        results: List[Dict[str, Any]] = []
        for root, dirs, files in os.walk(project_path):
            dirs[:] = [d for d in dirs if d not in _SKIP_DIRS]
            for fname in files:
                if exts and not any(fname.endswith(e) for e in exts):
                    continue
                if file_re and not file_re.search(fname):
                    continue
                fpath = os.path.join(root, fname)
                rel   = os.path.relpath(fpath, project_path)
                try:
                    with open(fpath, "r", encoding="utf-8", errors="ignore") as fh:
                        code = fh.read()
                    count = len(method_re.findall(code)) if method_re else 0
                except Exception:
                    count = 0
                results.append({"path": rel, "abs_path": fpath, "test_count": count})
        return results

    # ── test discovery ────────────────────────────────────────────────────────

    def _extract_tests(self, rel_path: str, code: str, language: str) -> List[Dict]:
        cfg = _LANG_CFG.get(language)
        if not cfg:
            return []
        cm = cfg["class_re"].search(code)
        class_name = (
            cm.group(1) if cm
            else os.path.splitext(os.path.basename(rel_path))[0]
        )
        tests = []
        for m in cfg["method_re"].finditer(code):
            name  = m.group(1)
            start = m.end()
            body  = code[start: start + _MAX_BODY_CHARS].strip()
            line  = code[: m.start()].count("\n") + 1
            tests.append({
                "class": class_name,
                "name":  name,
                "body":  body,
                "file":  rel_path,
                "line":  line,
            })
        return tests

    def _discover_from_disk(self, project_path: str, language: str) -> List[Dict]:
        cfg     = _LANG_CFG.get(language, {})
        file_re = cfg.get("file_re")
        exts    = cfg.get("exts", [])
        all_tests: List[Dict] = []
        files_found = 0
        for root, dirs, files in os.walk(project_path):
            dirs[:] = [d for d in dirs if d not in _SKIP_DIRS]
            for fname in files:
                if files_found >= _MAX_FILES:
                    break
                if exts and not any(fname.endswith(e) for e in exts):
                    continue
                if file_re and not file_re.search(fname):
                    continue
                fpath = os.path.join(root, fname)
                rel   = os.path.relpath(fpath, project_path)
                found = self._extract_tests(rel, self._read(fpath), language)
                if found:
                    all_tests.extend(found)
                    files_found += 1
        logger.info(f"Disk scan: {len(all_tests)} tests across {files_found} files")
        return all_tests

    def _discover_from_filemap(self, file_map: Dict[str, str], language: str) -> List[Dict]:
        cfg     = _LANG_CFG.get(language, {})
        file_re = cfg.get("file_re")
        exts    = cfg.get("exts", [])
        all_tests: List[Dict] = []
        for path, code in file_map.items():
            fname = os.path.basename(path)
            if exts and not any(fname.endswith(e) for e in exts):
                continue
            if file_re and not file_re.search(fname):
                continue
            all_tests.extend(self._extract_tests(path, code, language))
        logger.info(f"File-map scan: {len(all_tests)} tests from {len(file_map)} files")
        return all_tests

    # ── LLM conversion ────────────────────────────────────────────────────────

    def _build_prompt(self, batch: List[Dict]) -> str:
        payload = json.dumps(
            [
                {
                    "index": i,
                    "class": t["class"],
                    "name":  t["name"],
                    "body":  t["body"][:400],
                    "file":  t["file"],
                }
                for i, t in enumerate(batch)
            ],
            indent=2,
        )

        if self.output_format == "bdd":
            schema = """{
  "index":    <same integer>,
  "feature":  "<human-readable feature/module name>",
  "scenario": "<clear scenario title, not the raw method name>",
  "given":    ["<precondition step>", ...],
  "when":     ["<action step>", ...],
  "then":     ["<expected result step>", ...],
  "tags":     ["@smoke", "@regression", ...]
}"""
            instructions = (
                "Convert each test to BDD (Gherkin) format. "
                "No 'Given/When/Then' prefixes in the list strings."
            )

        elif self.output_format == "plain":
            schema = """{
  "index":           <same integer>,
  "title":           "<clear, readable test title>",
  "preconditions":   "<what must be true before the test>",
  "steps":           "<numbered action steps as a single string>",
  "expected_result": "<what should happen after the steps>",
  "priority":        "High | Medium | Low"
}"""
            instructions = (
                "Convert each test to a plain structured test case."
            )

        else:  # step_by_step
            schema = """{
  "index":  <same integer>,
  "title":  "<clear, readable test title>",
  "steps":  [
    {"step": 1, "action": "<what to do>", "expected": "<expected result>"},
    ...
  ]
}"""
            instructions = (
                "Convert each test into a step-by-step breakdown. "
                "Each atomic action becomes one step row."
            )

        return f"""You are a senior QA engineer.
{instructions}

Return a JSON ARRAY only — no markdown fences, no extra text.
Each element must match this schema:
{schema}

Tests:
{payload}"""

    def _stub_row(self, local_i: int, test: Dict) -> Dict:
        """Fallback stub when LLM conversion fails for a test."""
        readable = re.sub(r"[_\s]+", " ", test["name"]).strip()
        if self.output_format == "bdd":
            return {
                "index": local_i, "feature": test["class"], "scenario": readable,
                "given": ["system is in a valid state"],
                "when":  [f"'{test['name']}' is executed"],
                "then":  ["expected outcome is observed"],
                "tags":  [],
            }
        elif self.output_format == "plain":
            return {
                "index": local_i, "title": readable,
                "preconditions": "system is ready",
                "steps": f"1. Execute {test['name']}",
                "expected_result": "test passes",
                "priority": "Medium",
            }
        else:  # step_by_step
            return {
                "index": local_i, "title": readable,
                "steps": [{"step": 1, "action": f"Execute {test['name']}", "expected": "Test passes"}],
            }

    async def _convert_batch(self, batch: List[Dict]) -> List[Dict]:
        try:
            raw  = await self.llm.generate(self._build_prompt(batch))
            raw  = re.sub(r"```(?:json)?\s*", "", raw).strip().rstrip("`").strip()
            data = json.loads(raw)
            if isinstance(data, list):
                return data
        except Exception as exc:
            logger.warning(f"LLM batch conversion failed ({exc}); using stubs")
        return [self._stub_row(i, t) for i, t in enumerate(batch)]

    # ── row building ──────────────────────────────────────────────────────────

    def _to_rows(self, bdd_item: Dict, test: Dict, test_id: int) -> List[Dict]:
        """Convert one LLM result + its source metadata into Excel row(s)."""
        if self.output_format == "bdd":
            return [{
                "Feature":     bdd_item.get("feature", test["class"]),
                "Scenario":    bdd_item.get("scenario", test["name"]),
                "Given":       "\n".join(bdd_item.get("given", [])),
                "When":        "\n".join(bdd_item.get("when", [])),
                "Then":        "\n".join(bdd_item.get("then", [])),
                "Tags":        " ".join(bdd_item.get("tags", [])),
                "Source File": test["file"],
                "Line":        test["line"],
            }]

        elif self.output_format == "plain":
            return [{
                "Test ID":          f"TC-{test_id:04d}",
                "Title":            bdd_item.get("title", test["name"]),
                "Preconditions":    bdd_item.get("preconditions", ""),
                "Steps":            bdd_item.get("steps", ""),
                "Expected Result":  bdd_item.get("expected_result", ""),
                "Priority":         bdd_item.get("priority", "Medium"),
                "Source File":      test["file"],
                "Line":             test["line"],
            }]

        else:  # step_by_step — one row per step
            title  = bdd_item.get("title", test["name"])
            steps  = bdd_item.get("steps", [])
            if not steps:
                steps = [{"step": 1, "action": "Execute test", "expected": "Test passes"}]
            return [
                {
                    "Test ID":         f"TC-{test_id:04d}",
                    "Test Title":      title,
                    "Step #":          s.get("step", idx + 1),
                    "Action":          s.get("action", ""),
                    "Expected Result": s.get("expected", ""),
                    "Source File":     test["file"],
                    "Line":            test["line"],
                }
                for idx, s in enumerate(steps)
            ]

    async def _convert_all(self, tests: List[Dict]) -> List[Dict]:
        rows: List[Dict] = []
        test_id = 1
        for start in range(0, len(tests), _BATCH_SIZE):
            batch     = tests[start: start + _BATCH_SIZE]
            llm_items = await self._convert_batch(batch)
            by_index  = {item["index"]: item for item in llm_items if isinstance(item, dict)}
            for local_i, test in enumerate(batch):
                item = by_index.get(local_i, self._stub_row(local_i, test))
                rows.extend(self._to_rows(item, test, test_id))
                test_id += 1
        return rows

    # ── Excel builder ─────────────────────────────────────────────────────────

    def build_excel(self, rows: List[Dict]) -> bytes:
        try:
            import openpyxl
            from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
            from openpyxl.utils import get_column_letter
        except ImportError:
            raise RuntimeError("openpyxl is required: pip install openpyxl")

        columns = _FORMAT_COLUMNS[self.output_format]
        headers = [c[0] for c in columns]
        widths  = [c[1] for c in columns]

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Test Cases"

        HEADER_FILL = PatternFill("solid", fgColor="1F4E79")
        HEADER_FONT = Font(bold=True, color="FFFFFF", size=11)
        THIN        = Side(style="thin", color="BFBFBF")
        BORDER      = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
        WRAP        = Alignment(wrap_text=True, vertical="top")
        EVEN_FILL   = PatternFill("solid", fgColor="DCE6F1")
        ODD_FILL    = PatternFill("solid", fgColor="FFFFFF")

        for col_idx, header in enumerate(headers, start=1):
            cell = ws.cell(row=1, column=col_idx, value=header)
            cell.font      = HEADER_FONT
            cell.fill      = HEADER_FILL
            cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
            cell.border    = BORDER
        ws.row_dimensions[1].height = 22

        for row_idx, row_data in enumerate(rows, start=2):
            fill = EVEN_FILL if row_idx % 2 == 0 else ODD_FILL
            for col_idx, header in enumerate(headers, start=1):
                val  = row_data.get(header, "")
                cell = ws.cell(row=row_idx, column=col_idx, value=str(val) if val else "")
                cell.fill      = fill
                cell.alignment = WRAP
                cell.border    = BORDER

        for col_idx, width in enumerate(widths, start=1):
            ws.column_dimensions[get_column_letter(col_idx)].width = width

        ws.freeze_panes = "A2"
        ws.auto_filter.ref = f"A1:{get_column_letter(len(headers))}1"

        buf = io.BytesIO()
        wb.save(buf)
        return buf.getvalue()

    # ── main entry ────────────────────────────────────────────────────────────

    async def process(
        self,
        input_data: Any = None,
        project_path: Optional[str] = None,
        existing_files: Optional[Dict[str, str]] = None,
        max_tests: int = 500,
    ) -> Dict[str, Any]:
        """
        Scan tests → convert to chosen format → build Excel.

        Returns:
            excel_b64       — base64-encoded .xlsx bytes
            excel_filename  — suggested filename
            total_scenarios — number of Excel rows generated
            features        — sorted unique feature/class names discovered
            summary         — human-readable summary string
        """
        language = self._detect_language(project_path, existing_files)
        logger.info(f"TestAnalyserAgent: language={language}, format={self.output_format}")

        if existing_files:
            tests = self._discover_from_filemap(existing_files, language)
        elif project_path:
            tests = self._discover_from_disk(project_path, language)
        else:
            return {
                "excel_b64": "", "excel_filename": "",
                "total_scenarios": 0, "features": [],
                "summary": "No project_path or existing_files provided.",
            }

        if len(tests) > max_tests:
            logger.warning(f"Capping {len(tests)} tests to max_tests={max_tests}")
            tests = tests[:max_tests]

        if not tests:
            hints = {
                "python":     "test_*.py or *_test.py files",
                "java":       "*Test.java / *IT.java with @Test methods",
                "javascript": "*.spec.ts / *.test.js with it() or test() blocks",
                "c#":         "*Tests.cs with [Test] / [Fact] attributes",
            }
            return {
                "excel_b64": "", "excel_filename": "",
                "total_scenarios": 0, "features": [],
                "summary": (
                    f"No {language} test files found. "
                    f"Expected: {hints.get(language, 'test files')}."
                ),
            }

        logger.info(f"Converting {len(tests)} tests → format={self.output_format}")
        rows = await self._convert_all(tests)

        excel_bytes    = self.build_excel(rows)
        excel_b64      = base64.b64encode(excel_bytes).decode()
        excel_filename = f"test_analysis_{self.output_format}.xlsx"

        # Unique feature/class names depend on format
        if self.output_format == "bdd":
            features = sorted({r.get("Feature", "") for r in rows} - {""})
        else:
            features = sorted({t["class"] for t in tests})

        summary = (
            f"Analysed {len(tests)} test(s) from {len(features)} class(es)/feature(s). "
            f"Format: {self.output_format}. Rows in Excel: {len(rows)}.\n"
            f"Classes/Features: {', '.join(features[:10])}"
            + (" …" if len(features) > 10 else "")
        )
        logger.info(summary)

        return {
            "excel_b64":       excel_b64,
            "excel_filename":  excel_filename,
            "total_scenarios": len(rows),
            "features":        features,
            "summary":         summary,
        }
