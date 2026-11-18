from quality_engineering_agentic_framework.utils.code_validation import (
    failure_reason,
    validate_and_format,
)


def test_valid_python_passes():
    files, report = validate_and_format({"ok.py": "def f():\n    return 1\n"})
    assert report[0]["ok"] is True
    assert any("syntax: ok" in c for c in report[0]["checks"])


def test_python_syntax_error_is_a_hard_failure_with_line_number():
    files, report = validate_and_format({"bad.py": "def f(:\n    return 1\n"})
    entry = report[0]
    assert entry["ok"] is False
    assert "line 1" in failure_reason(entry)


def test_unbalanced_brackets_are_reported_but_not_a_hard_failure():
    # Documented behaviour: bracket balance is only a hint for non-Python files.
    files, report = validate_and_format({"A.java": "class A { void m() { }"})
    assert any("unclosed" in c for c in report[0]["checks"])
    assert report[0]["ok"] is True


def test_validation_never_raises_and_reports_each_file():
    files, report = validate_and_format({"a.py": "x = 1\n", "b.txt": "plain text"})
    assert {e["file"] for e in report} == {"a.py", "b.txt"}
    assert set(files) == {"a.py", "b.txt"}
