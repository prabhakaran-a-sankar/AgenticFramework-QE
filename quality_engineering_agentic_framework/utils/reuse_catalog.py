"""
Reuse catalog + reuse check for generated automation.

  build_catalog(file_map)      -> what reusable things already exist: classes/methods,
                                  module functions, test FIXTURES (Playwright test.extend,
                                  pytest) and Gherkin STEP DEFINITIONS / feature files
  render_catalog(catalog, kw)  -> a ranked, size-bounded list of classes/methods/fixtures
  render_steps(catalog, kw)    -> a ranked list of existing step phrases (Gherkin projects)
  check_calls(files, catalog)  -> calls to methods, and Gherkin steps, that exist neither in
                                  the project nor in the generated files

Pure, dependency-free and best-effort: regex based (Java, Python, JS/TS, C#, Gherkin), never
raises, and its findings are WARNINGS, not proof. A class that extends something we cannot see
(a library base class) is never flagged, because the method may be inherited.
"""

import difflib
import os
import re
from typing import Any, Dict, Iterable, List, Optional, Set

_EXT_LANG = {".java": "java", ".py": "python", ".js": "javascript", ".jsx": "javascript",
             ".ts": "javascript", ".tsx": "javascript", ".cs": "c#", ".feature": "gherkin"}

_SKIP_DIRS = {".git", "node_modules", "target", "build", "dist", "bin", "obj", "venv", ".venv",
              "__pycache__", ".idea", ".vscode", ".pytest_cache", "test-output",
              "allure-results", "reports", ".gradle", "out"}

# Words that say nothing about which method fits a task.
_STOP = {"the", "and", "for", "are", "not", "all", "its", "has", "can", "but", "that", "with",
         "from", "this", "test", "tests", "spec", "specs", "write", "create", "generate",
         "automation", "script", "scripts", "case", "cases", "page", "check", "verify"}

# Methods that are tests / lifecycle hooks / fixtures — not something to call from a new test.
_NOT_REUSABLE_ANNOTATION = re.compile(
    r"@(?:Test|ParameterizedTest|RepeatedTest|Before|After|BeforeEach|AfterEach|BeforeAll|AfterAll|"
    r"BeforeMethod|AfterMethod|BeforeClass|AfterClass|BeforeTest|AfterTest|DataProvider|Fact|Theory|"
    r"TestMethod|TestInitialize|TestCleanup|pytest\.fixture|fixture)\b|"
    r"\[(?:Test|TestCase|SetUp|TearDown|Fact|Theory|TestMethod|OneTimeSetUp|OneTimeTearDown)\b")

_OBJECT_METHODS = {"toString", "equals", "hashCode", "getClass", "wait", "notify", "notifyAll",
                   "ToString", "Equals", "GetHashCode", "GetType"}

_RET = r"[\w.?]+(?:<[^>]*>)?(?:\[\])*"
_JAVA_CLASS = re.compile(r"\b(?:class|interface|enum|record)\s+(\w+)(?:\s*<[^>{]*>)?(?:\s+extends\s+(\w+))?")
_JAVA_METHOD = re.compile(
    r"\b(?:public|protected)\s+(?:static\s+)?(?:final\s+)?(?:abstract\s+)?(?:synchronized\s+)?"
    r"(?:<[^>]+>\s+)?" + _RET + r"\s+(\w+)\s*\(([^)]*)\)")
_CS_CLASS = re.compile(r"\b(?:class|interface|struct)\s+(\w+)(?:\s*<[^>{]*>)?(?:\s*:\s*(\w+))?")
_CS_METHOD = re.compile(
    r"\b(?:public|protected|internal)\s+(?:static\s+)?(?:virtual\s+|override\s+|async\s+)*"
    + _RET + r"\s+(\w+)\s*\(([^)]*)\)")
_PY_CLASS = re.compile(r"^([ \t]*)class\s+(\w+)\s*(?:\(([^)]*)\))?\s*:", re.M)
_PY_DEF = re.compile(r"^([ \t]*)(?:async\s+)?def\s+(\w+)\s*\(([^)]*)\)", re.M)
_JS_CLASS = re.compile(r"\bclass\s+(\w+)(?:\s+extends\s+(\w+))?")
_JS_METHOD = re.compile(
    r"^[ \t]+(?:static\s+)?(?:async\s+)?(?:get\s+|set\s+)?(\w+)\s*\(([^)]*)\)\s*(?::\s*[\w<>\[\]|. ]+)?\s*\{", re.M)
_JS_FUNC = re.compile(r"^(?:export\s+)?(?:default\s+)?(?:async\s+)?function\s+(\w+)\s*\(([^)]*)\)", re.M)
_JS_ARROW = re.compile(r"^(?:export\s+)?const\s+(\w+)\s*=\s*(?:async\s*)?\(([^)]*)\)\s*(?::[^=]+)?=>", re.M)
_JS_KEYWORDS = {"if", "for", "while", "switch", "catch", "function", "return", "constructor",
                "else", "do", "try", "with", "describe", "it", "test", "expect"}

# Gherkin step definitions in the host language
_STEP_JAVA = re.compile(r'@(Given|When|Then|And|But)\(\s*"((?:[^"\\]|\\.)*)"')
_STEP_CS = re.compile(r'\[(Given|When|Then)\(\s*(@?)"((?:[^"\\]|\\.|"")*)"\s*\)\]')
_STEP_PY = re.compile(r"@(given|when|then|step)\(\s*[uUrR]?(['\"])((?:\\.|(?!\2).)*)\2", re.I)
_STEP_JS = re.compile(r"(?<![\w.@])(Given|When|Then)\(\s*(?:(['\"`])((?:\\.|(?!\2).)*)\2|/((?:\\.|[^/\n])+)/)")
_FEATURE_STEP = re.compile(r"^\s*(Given|When|Then|And|But|\*)\s+(.*\S)\s*$")
_SCENARIO = re.compile(r"^\s*(Scenario Outline|Scenario Template|Scenario|Example):\s*(.*)$")


def language_of(path: str) -> Optional[str]:
    return _EXT_LANG.get(os.path.splitext(path)[1].lower())


def tokens(text: str) -> Set[str]:
    """camelCase / snake_case / digits -> lowercase words (>2 chars)."""
    parts = re.findall(r"[A-Z]+(?![a-z])|[A-Z]?[a-z]+|\d+", text or "")
    return {p.lower() for p in parts if len(p) > 2}


def task_keywords(text: str) -> Set[str]:
    return {w.lower() for w in re.findall(r"[A-Za-z]{3,}", text or "")} - _STOP


class Catalog:
    """classes:   name -> {file, language, bases, methods{name: params}}
       functions: file -> {name: params}                 (module-level functions)
       fixtures:  name -> {file, class|None}             (Playwright test.extend / pytest)
       steps:     [{keyword, pattern, file, regex}]      (Gherkin step definitions)
       features:  [{file, feature, scenarios, steps[{line, keyword, text}]}]"""

    def __init__(self) -> None:
        self.classes: Dict[str, Dict[str, Any]] = {}
        self.functions: Dict[str, Dict[str, str]] = {}
        self.fixtures: Dict[str, Dict[str, Any]] = {}
        self.steps: List[Dict[str, Any]] = []
        self.features: List[Dict[str, Any]] = []

    def add_class(self, name: str, path: str, lang: str, bases: Iterable[str],
                  methods: Dict[str, str]) -> None:
        info = self.classes.setdefault(name, {"file": path, "language": lang, "bases": [], "methods": {}})
        for b in bases:
            if b and b not in info["bases"]:
                info["bases"].append(b)
        info["methods"].update(methods)

    def merged_with(self, other: "Catalog") -> "Catalog":
        out = Catalog()
        for src in (self, other):
            for name, i in src.classes.items():
                out.add_class(name, i["file"], i["language"], i["bases"], dict(i["methods"]))
            for f, fns in src.functions.items():
                out.functions.setdefault(f, {}).update(fns)
            out.fixtures.update(src.fixtures)
            for s in src.steps:
                if not any(s["pattern"] == t["pattern"] and s["file"] == t["file"] for t in out.steps):
                    out.steps.append(s)
            out.features.extend(src.features)
        return out

    def resolve_methods(self, name: str, _seen: Optional[Set[str]] = None):
        """(methods incl. inherited, fully_resolved). fully_resolved is False when a base
        class is outside the catalog (a library class), so the method list is incomplete."""
        _seen = _seen or set()
        info = self.classes.get(name)
        if not info or name in _seen:
            return set(), info is not None
        _seen.add(name)
        methods, resolved = set(info["methods"]), True
        for base in info["bases"]:
            if base in ("Object", "object"):
                continue
            if base in self.classes:
                m, r = self.resolve_methods(base, _seen)
                methods |= m
                resolved = resolved and r
            else:
                resolved = False
        return methods, resolved


# ---------------------------------------------------------------------------
# Extraction
# ---------------------------------------------------------------------------

def _py_decorators(code: str, pos: int) -> str:
    """The decorator lines directly above the `def` that starts at `pos`."""
    attached = []
    for line in reversed(code[:pos].splitlines()):
        if not line.strip().startswith("@"):
            break
        attached.append(line)
    return "\n".join(attached)


def _py_body(code: str, m: "re.Match") -> str:
    indent, body = len(m.group(1)), []
    for line in code[m.end():].splitlines()[1:]:
        if line.strip() and (len(line) - len(line.lstrip())) <= indent:
            break
        body.append(line)
        if len(body) > 40:
            break
    return "\n".join(body)


def _reusable(code: str, pos: int, lang: str = "") -> bool:
    """False for tests, lifecycle hooks and fixtures — judged only by the annotations or
    decorators attached directly to THIS method, never by a neighbour's."""
    if lang == "python":
        return not _NOT_REUSABLE_ANNOTATION.search(_py_decorators(code, pos))
    head = code[max(0, pos - 300):pos]
    segment = head[max(head.rfind("}"), head.rfind(";"), head.rfind("{")) + 1:]
    return not _NOT_REUSABLE_ANNOTATION.search(segment)


def _match_close(code: str, start: int, open_ch: str, close_ch: str) -> int:
    """Index of the bracket closing the one at `start` (quote aware); -1 if there is none."""
    depth, i, quote = 0, start, None
    while i < len(code):
        ch = code[i]
        if quote:
            if ch == "\\":
                i += 1
            elif ch == quote:
                quote = None
        elif ch in "'\"`":
            quote = ch
        elif ch == open_ch:
            depth += 1
        elif ch == close_ch and not (close_ch == ">" and code[i - 1:i] == "="):   # skip '=>'
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return -1


def _split_top_level(body: str) -> List[str]:
    parts, depth, cur, quote, i = [], 0, [], None, 0
    while i < len(body):
        ch = body[i]
        if quote:
            cur.append(ch)
            if ch == "\\":
                cur.append(body[i + 1:i + 2])
                i += 1
            elif ch == quote:
                quote = None
        elif ch in "'\"`":
            quote = ch
            cur.append(ch)
        elif ch in "{[(":
            depth += 1
            cur.append(ch)
        elif ch in "}])":
            depth -= 1
            cur.append(ch)
        elif ch == "," and depth == 0:
            parts.append("".join(cur))
            cur = []
        else:
            cur.append(ch)
        i += 1
    if "".join(cur).strip():
        parts.append("".join(cur))
    return parts


def _js_fixtures(path: str, code: str, cat: Catalog) -> None:
    """Playwright: `base.extend<...>({ loginPage: async ({ page }, use) => { await use(new LoginPage(page)) } })`."""
    for m in re.finditer(r"\.extend\b", code):
        i = m.end()
        while i < len(code) and code[i].isspace():
            i += 1
        if i < len(code) and code[i] == "<":
            j = _match_close(code, i, "<", ">")
            if j < 0:
                continue
            i = j + 1
            while i < len(code) and code[i].isspace():
                i += 1
        if i >= len(code) or code[i] != "(":
            continue
        i += 1
        while i < len(code) and code[i].isspace():
            i += 1
        if i >= len(code) or code[i] != "{":
            continue
        end = _match_close(code, i, "{", "}")
        if end < 0:
            continue
        for part in _split_top_level(code[i + 1:end]):
            key = re.match(r"\s*(?:\[\s*)?['\"]?(\w+)['\"]?\s*:", part)
            if key:
                cls = re.search(r"\bnew\s+([A-Z]\w*)\s*\(", part)
                cat.fixtures[key.group(1)] = {"file": path, "class": cls.group(1) if cls else None}


def _unescape(s: str) -> str:
    return re.sub(r'\\(["\\])', r"\1", s)


def _extract_steps(path: str, code: str, lang: str, cat: Catalog) -> None:
    found = []
    if lang == "java":
        found = [(m.group(1), _unescape(m.group(2)), False) for m in _STEP_JAVA.finditer(code)]
    elif lang == "c#":
        found = [(m.group(1), m.group(3).replace('""', '"') if m.group(2) else _unescape(m.group(3)), False)
                 for m in _STEP_CS.finditer(code)]
    elif lang == "python":
        found = [(m.group(1).capitalize(), m.group(3), False) for m in _STEP_PY.finditer(code)]
    elif lang == "javascript":
        found = [(m.group(1), m.group(3) if m.group(3) is not None else m.group(4), m.group(3) is None)
                 for m in _STEP_JS.finditer(code)]
    for keyword, pattern, is_regex in found:
        cat.steps.append({"keyword": keyword, "pattern": pattern, "file": path, "regex": is_regex})


def parse_feature(code: str) -> Dict[str, Any]:
    """Feature title, scenario titles and step lines (with line numbers) of a .feature file."""
    feature, scenarios, steps, in_doc = "", [], [], False
    for n, line in enumerate((code or "").splitlines(), 1):
        s = line.strip()
        if s.startswith('"""') or s.startswith("```"):
            in_doc = not in_doc
            continue
        if in_doc or not s or s[0] in "#|@":
            continue
        m = re.match(r"Feature:\s*(.*)", s)
        if m and not feature:
            feature = m.group(1)
            continue
        m = _SCENARIO.match(line)
        if m:
            scenarios.append(m.group(2).strip())
            continue
        m = _FEATURE_STEP.match(line)
        if m:
            steps.append({"line": n, "keyword": m.group(1), "text": m.group(2)})
    return {"feature": feature, "scenarios": scenarios, "steps": steps[:400]}


def _extract(path: str, code: str, lang: str, cat: Catalog) -> None:
    if lang == "gherkin":
        cat.features.append({"file": path, **parse_feature(code)})
        return
    if lang in ("java", "c#"):
        cls_re, m_re = (_JAVA_CLASS, _JAVA_METHOD) if lang == "java" else (_CS_CLASS, _CS_METHOD)
        classes = [(m.start(), m.group(1), m.group(2)) for m in cls_re.finditer(code)]
        per_class: Dict[str, Dict[str, str]] = {}
        for m in m_re.finditer(code):
            owner = next(((n, b) for p, n, b in reversed(classes) if p < m.start()), None)
            if owner and _reusable(code, m.start()):
                per_class.setdefault(owner[0], {})[m.group(1)] = " ".join(m.group(2).split())
        for _, name, base in classes:
            cat.add_class(name, path, lang, [base], per_class.get(name, {}))
    elif lang == "python":
        classes = [(m.start(), len(m.group(1)), m.group(2), m.group(3) or "") for m in _PY_CLASS.finditer(code)]
        per_class = {}
        for m in _PY_DEF.finditer(code):
            name, indent = m.group(2), len(m.group(1))
            owner = next(((n, i) for p, i, n, _ in reversed(classes) if p < m.start() and i < indent), None)
            if owner and 0 < indent - owner[1] <= 8:
                if (not name.startswith("_") and not name.startswith("test")
                        and _reusable(code, m.start(), "python")):
                    per_class.setdefault(owner[0], {})[name] = " ".join(m.group(3).split())
            elif indent == 0 and not name.startswith("_") and not name.startswith("test"):
                if _reusable(code, m.start(), "python"):
                    cat.functions.setdefault(path, {})[name] = " ".join(m.group(3).split())
            if re.search(r"@(?:pytest\.)?fixture\b", _py_decorators(code, m.start())):
                cls = re.search(r"\b(?:return|yield)\s+([A-Z]\w*)\s*\(", _py_body(code, m))
                cat.fixtures[name] = {"file": path, "class": cls.group(1) if cls else None}
        for _, _, name, bases in classes:
            cat.add_class(name, path, lang, [b.strip().split(".")[-1] for b in bases.split(",") if b.strip()],
                          per_class.get(name, {}))
    else:  # javascript / typescript
        classes = [(m.start(), m.group(1), m.group(2)) for m in _JS_CLASS.finditer(code)]
        per_class = {}
        for m in _JS_METHOD.finditer(code):
            owner = next(((n, b) for p, n, b in reversed(classes) if p < m.start()), None)
            if owner and m.group(1) not in _JS_KEYWORDS:
                per_class.setdefault(owner[0], {})[m.group(1)] = " ".join(m.group(2).split())
        for _, name, base in classes:
            cat.add_class(name, path, lang, [base], per_class.get(name, {}))
        for rx in (_JS_FUNC, _JS_ARROW):
            for m in rx.finditer(code):
                if m.group(1) not in _JS_KEYWORDS:
                    cat.functions.setdefault(path, {})[m.group(1)] = " ".join(m.group(2).split())
        _js_fixtures(path, code, cat)
    _extract_steps(path, code, lang, cat)


def build_catalog(file_map: Optional[Dict[str, str]]) -> Catalog:
    cat = Catalog()
    for path, code in (file_map or {}).items():
        lang = language_of(path)
        if not lang or not code:
            continue
        try:
            _extract(path, code, lang, cat)
        except Exception:      # never let catalog building break generation
            continue
    return cat


def load_project_files(project_path: str, max_files: int = 250, max_file_bytes: int = 200_000) -> Dict[str, str]:
    """Read source files (known extensions) from disk for building a catalog."""
    out: Dict[str, str] = {}
    for root, dirs, files in os.walk(project_path):
        dirs[:] = [d for d in dirs if d not in _SKIP_DIRS]
        for f in files:
            if len(out) >= max_files:
                return out
            if os.path.splitext(f)[1].lower() in _EXT_LANG:
                full = os.path.join(root, f)
                try:
                    if os.path.getsize(full) <= max_file_bytes:
                        with open(full, "r", encoding="utf-8", errors="ignore") as fh:
                            out[os.path.relpath(full, project_path)] = fh.read()
                except OSError:
                    continue
    return out


# ---------------------------------------------------------------------------
# Rendering (for the prompt)
# ---------------------------------------------------------------------------

def render_catalog(cat: Catalog, keywords: Iterable[str], max_chars: int = 3500,
                   max_methods_per_class: int = 12) -> str:
    """Ranked 'what already exists' list: fixtures, then the most task-relevant classes first."""
    kws = set(keywords) - _STOP
    lines, used = [], 0
    if cat.fixtures:
        ranked = sorted(cat.fixtures.items(), key=lambda kv: -len(tokens(kv[0]) & kws))
        shown = ", ".join(n + (f" → {i['class']}" if i["class"] else "") for n, i in ranked[:20])
        line = ("  FIXTURES (ask for them as test parameters, don't construct them yourself): "
                + shown[:600])
        lines.append(line)
        used += len(line) + 1
    rows = []
    for order, (name, info) in enumerate(cat.classes.items()):
        if not info["methods"]:
            continue
        ctok = tokens(name)
        scored = sorted(((-(len(tokens(m) & kws) * 2 + len(ctok & kws)), i, m, p)
                         for i, (m, p) in enumerate(info["methods"].items())))
        rows.append((scored[0][0], order, name, info, scored))     # [0][0] = best (negated) score
    for order, (path, fns) in enumerate(cat.functions.items(), start=len(rows)):
        if not fns:
            continue
        scored = sorted(((-(len(tokens(m) & kws) * 2), i, m, p) for i, (m, p) in enumerate(fns.items())))
        rows.append((scored[0][0], order, f"{os.path.basename(path)} (functions)", {"file": path}, scored))
    for _, _, name, info, scored in sorted(rows, key=lambda r: (r[0], r[1])):
        shown = ", ".join(f"{m}({p})" for _, _, m, p in scored[:max_methods_per_class])
        extra = len(scored) - max_methods_per_class
        line = f"  {name} [{info['file']}]: {shown}" + (f", … +{extra} more" if extra > 0 else "")
        if used + len(line) > max_chars:
            lines.append("  … (more classes omitted)")
            break
        lines.append(line)
        used += len(line) + 1
    return "\n".join(lines)


def render_steps(cat: Catalog, keywords: Iterable[str], max_chars: int = 3000) -> str:
    """Existing Gherkin step phrases, the most task-relevant first. Uses the step
    definitions; if none are visible, falls back to the steps used in existing features."""
    kws = set(keywords) - _STOP
    items = []
    if cat.steps:
        items = [(s["keyword"], s["pattern"], s["file"]) for s in cat.steps]
    else:
        seen = set()
        for f in cat.features:
            for st in f["steps"]:
                if st["text"] not in seen:
                    seen.add(st["text"])
                    items.append((st["keyword"], st["text"], f["file"]))
    ranked = sorted(enumerate(items), key=lambda t: (-len(tokens(t[1][1]) & kws), t[0]))
    lines, used = [], 0
    for _, (kw, pattern, file) in ranked:
        line = f"  {kw} {pattern}   [{file}]"
        if used + len(line) > max_chars:
            lines.append("  … (more steps omitted)")
            break
        lines.append(line)
        used += len(line) + 1
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Gherkin step matching
# ---------------------------------------------------------------------------

_EXPR_TYPES = {"string": r"(?:\"[^\"]*\"|'[^']*')", "int": r"-?\d+", "float": r"-?\d*\.?\d+",
               "word": r"\S+", "": r".*"}


def step_regex(pattern: str, is_regex: bool = False) -> Optional["re.Pattern"]:
    """Compile a step definition (regex, Cucumber expression or behave/parse style) into a
    regex that matches whole step text. None if it cannot be compiled."""
    try:
        looks_regex = is_regex or pattern.startswith("^") or pattern.endswith("$") or bool(
            re.search(r"\(\[|\(\\d|\\d|\\w|\.\*|\(\.\+\)|\[\^|\(\?:", pattern))
        if looks_regex:
            p = pattern if pattern.startswith("^") else "^" + pattern
            return re.compile(p if p.endswith("$") else p + "$")
        # Cucumber expression / parse style: {string} {int} {name} (optional) a/b
        p = re.sub(r"(?<![\w/])(\w+)/(\w+)(?![\w/])", lambda m: f"\x00(?:{m.group(1)}|{m.group(2)})\x00", pattern)
        out = []
        for idx, chunk in enumerate(p.split("\x00")):
            if idx % 2:                      # an alternation group, already regex
                out.append(chunk)
                continue
            i = 0
            while i < len(chunk):
                ch = chunk[i]
                if ch == "{" and chunk.find("}", i) != -1:
                    j = chunk.find("}", i)
                    out.append(_EXPR_TYPES.get(chunk[i + 1:j].split(":")[0], r".+?"))
                    i = j + 1
                elif ch == "(" and chunk.find(")", i) != -1:
                    j = chunk.find(")", i)
                    out.append("(?:" + re.escape(chunk[i + 1:j]) + ")?")
                    i = j + 1
                else:
                    out.append(re.escape(ch))
                    i += 1
        return re.compile("^" + "".join(out) + "$")
    except re.error:
        return None


def _step_matches(text: str, regexes: List["re.Pattern"]) -> bool:
    variants = [text, re.sub(r'"<[^>]+>"', '"VALUE"', text), re.sub(r"<[^>]+>", "VALUE", text),
                re.sub(r"<[^>]+>", '"VALUE"', text)]
    return any(r.match(v) for r in regexes for v in variants)


# ---------------------------------------------------------------------------
# Reuse check
# ---------------------------------------------------------------------------

_BIND = {
    "java": re.compile(r"\b(\w+)\s*=\s*new\s+([A-Z]\w*)\s*[(<]"),
    "c#": re.compile(r"\b(\w+)\s*=\s*new\s+([A-Z]\w*)\s*[(<]"),
    "javascript": re.compile(r"\b(\w+)\s*=\s*(?:await\s+)?new\s+([A-Z]\w*)\s*\("),
    "python": re.compile(r"(?<![\w.])(?:self\.)?(\w+)\s*=\s*([A-Z]\w*)\("),
}
_JS_DESTRUCTURED = re.compile(r"\(\s*\{\s*([^{}()]*?)\s*\}\s*(?:,[^()]*)?\)\s*(?:=>|\{)")
_PY_TEST_PARAMS = re.compile(r"def\s+test\w*\(([^)]*)\)")


def _fixture_params(code: str, lang: str) -> Set[str]:
    """Names a test asks for as parameters / destructured fixtures."""
    names: Set[str] = set()
    if lang == "javascript":
        for m in _JS_DESTRUCTURED.finditer(code):
            for part in m.group(1).split(","):
                n = re.split(r"[:=]", part.strip())[0].strip()
                if n.isidentifier():
                    names.add(n)
    elif lang == "python":
        for m in _PY_TEST_PARAMS.finditer(code):
            for part in m.group(1).split(","):
                n = re.split(r"[:=]", part.strip())[0].strip()
                if n.isidentifier():
                    names.add(n)
    return names


def check_calls(files: Dict[str, str], existing: Optional[Catalog]) -> List[Dict[str, Any]]:
    """Warnings for generated code that uses something that exists nowhere:
      - `loginPage.clickSubmit()` / `LoginPage.helper()` where the class (or fixture's class)
        is known but the method is defined neither in the project nor in the generated files
      - a Gherkin step that matches no step definition (existing or generated)."""
    if existing is None:
        return []
    full = existing.merged_with(build_catalog(files))
    findings: List[Dict[str, Any]] = []
    for path, code in (files or {}).items():
        lang = language_of(path)
        if not lang or not code or lang == "gherkin":
            continue
        binds = {m.group(1): m.group(2) for m in _BIND[lang].finditer(code)}
        for name in _fixture_params(code, lang):                       # fixtures injected into tests
            info = full.fixtures.get(name)
            if info and info.get("class"):
                binds.setdefault(name, info["class"])
        calls = []                                                    # (class, method, position)
        for var, cls in binds.items():
            if cls in full.classes:
                prefix = r"(?<![\w.])(?:self\.)?" if lang == "python" else r"(?<![\w.])"
                for c in re.finditer(prefix + re.escape(var) + r"\.(\w+)\s*\(", code):
                    calls.append((cls, c.group(1), c.start()))
        for cls in full.classes:
            for c in re.finditer(r"(?<![\w.])" + re.escape(cls) + r"\.(\w+)\s*\(", code):
                calls.append((cls, c.group(1), c.start()))
        seen = set()
        for cls, method, pos in calls:
            methods, resolved = full.resolve_methods(cls)
            if method in methods or method in _OBJECT_METHODS or not resolved or (cls, method, pos) in seen:
                continue
            seen.add((cls, method, pos))
            findings.append({
                "kind": "method", "file": path, "line": code.count("\n", 0, pos) + 1,
                "class": cls, "method": method,
                "suggestions": difflib.get_close_matches(method, sorted(methods), n=3, cutoff=0.5),
                "message": (f"`{cls}.{method}()` is not defined in the existing code or in the "
                            f"generated files — reuse an existing method or add it to `{cls}`."),
            })

    # Gherkin: every step in a generated .feature file needs a step definition
    regexes = [r for r in (step_regex(s["pattern"], s["regex"]) for s in full.steps) if r]
    if regexes:
        patterns = [s["pattern"] for s in full.steps]
        for path, code in (files or {}).items():
            if language_of(path) != "gherkin":
                continue
            for st in parse_feature(code)["steps"]:
                if not _step_matches(st["text"], regexes):
                    findings.append({
                        "kind": "step", "file": path, "line": st["line"], "class": "", "method": "",
                        "step": f"{st['keyword']} {st['text']}",
                        "suggestions": difflib.get_close_matches(st["text"], patterns, n=3, cutoff=0.4),
                        "message": (f"step `{st['keyword']} {st['text']}` matches no existing step "
                                    f"definition and none was added — reuse an existing step phrase "
                                    f"or add a step definition for it."),
                    })
    return findings
