"""
log_parser.py — parses raw automation failure logs into structured failures.

Usage:
    from log_parser import parse
    result = parse(raw_log_string)
    print(result.exception_type, result.message, result.root_file, result.root_line)
"""

import re
from dataclasses import dataclass

FRAMEWORK_PACKAGES = {
    # Python test frameworks
    "pytest", "unittest", "_pytest", "pluggy", "_pytest.runner",
    # Java test frameworks
    "java.lang.reflect", "sun.reflect", "org.junit", "com.google.common",
    # JS/Node
    "node_modules/jest", "node_modules/mocha",
}

@dataclass
class ParsedFailure:
    exception_type: str     # e.g. "AssertionError"
    message: str            # e.g. "Expected 200, got 502"
    root_file: str          # first non-framework frame filename
    root_line: int          # line number
    expected: str | None    # parsed from assertion message
    actual: str | None      # parsed from assertion message
    raw_log: str            # original untouched log


def parse(raw_log: str) -> ParsedFailure:
    lines = raw_log.strip().splitlines()
    exception_type, message = _extract_exception(lines)
    root_file, root_line = _find_root_frame(lines)
    expected, actual = _extract_diff(message)
    return ParsedFailure(
        exception_type=exception_type,
        message=message,
        root_file=root_file,
        root_line=root_line,
        expected=expected,
        actual=actual,
        raw_log=raw_log,
    )


def _extract_exception(lines: list[str]) -> tuple[str, str]:
    """Scan from bottom up — last exception line is the real one."""
    for line in reversed(lines):
        m = re.match(r'^(\w[\w.]*(?:Error|Exception|Failure|Warning)): (.+)$', line.strip())
        if m:
            return m.group(1), m.group(2)
    return "UnknownError", lines[-1].strip() if lines else ""


def _find_root_frame(lines: list[str]) -> tuple[str, int]:
    """First stack frame that is NOT from a test framework package."""
    for line in lines:
        # Python: '  File "path/to/file.py", line 42, in test_name'
        m = re.match(r'\s+File "(.+)", line (\d+)', line)
        if m:
            filepath = m.group(1)
            if not any(pkg in filepath for pkg in FRAMEWORK_PACKAGES):
                return filepath.split("/")[-1], int(m.group(2))
        # Java: '\tat com.example.PaymentService.charge(PaymentService.java:88)'
        m2 = re.match(r'\s+at ([\w.]+)\((\w+\.java):(\d+)\)', line)
        if m2:
            cls = m2.group(1)
            if not any(pkg in cls for pkg in FRAMEWORK_PACKAGES):
                return m2.group(2), int(m2.group(3))
    return "unknown", 0


def _extract_diff(message: str) -> tuple[str | None, str | None]:
    """Pull expected/actual from common assertion message patterns."""
    patterns = [
        r'[Ee]xpected[: ]+(.+?)(?:,| but(?: was)?)[: ]+(.+)',   # "Expected X, got Y"
        r'[Aa]ssert(?:ion)? (.+?) == (.+)',                       # "assert X == Y"
        r'expected:\s*<(.+?)>\s*but was:\s*<(.+?)>',             # JUnit style
    ]
    for pat in patterns:
        m = re.search(pat, message)
        if m:
            return m.group(1).strip(), m.group(2).strip()
    return None, None


# ── Quick test ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    sample = """
    FAILED checkout_test.py::test_payment_gateway
    Traceback (most recent call last):
      File "/app/.venv/lib/pytest/runner.py", line 340, in _call_with_pyfunc
        result = func()
      File "/app/tests/checkout_test.py", line 42, in test_payment_gateway
        assert response.status_code == 200
    AssertionError: Expected 200, got 502
    """
    result = parse(sample)
    print(f"Type:     {result.exception_type}")
    print(f"Message:  {result.message}")
    print(f"File:     {result.root_file} : line {result.root_line}")
    print(f"Expected: {result.expected}  →  Actual: {result.actual}")
