#!/usr/bin/env python3
"""
Generic test runner for Python scripts that use input().

USAGE
-----
Run all tests:
    python tests/test_runner.py

Exit code 0 = all passed, 1 = one or more failures.

ADDING NEW TESTS
----------------
Append an entry to TEST_REGISTRY:

    ("scripts/your_script.py", [
        TestCase("description", "stdin input\\n", "expected stdout"),
        TestCase("generated output", "3\\n", some_callable),
    ])

The `expected` field accepts:
  - A plain string (exact match after newline normalization)
  - A callable(input_str: str) -> str  for dynamically generated output
"""

import subprocess
import sys
import os
from dataclasses import dataclass
from typing import Callable, List, Tuple, Union

# Resolve paths relative to the project root (one level up from tests/)
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@dataclass
class TestCase:
    description: str
    input: str
    expected: Union[str, Callable[[str], str]]
    timeout: int = 5


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------

def _normalize(text: str) -> str:
    """Normalize line endings and strip trailing newline."""
    return text.replace("\r\n", "\n").rstrip("\n")


def _resolve_expected(tc: TestCase) -> str:
    if callable(tc.expected):
        return _normalize(tc.expected(tc.input))
    return _normalize(tc.expected)


def run_test(script_path: str, tc: TestCase) -> Tuple[bool, str]:
    """Run one test case. Returns (passed, detail_message)."""
    abs_path = os.path.join(PROJECT_ROOT, script_path)
    if not os.path.isfile(abs_path):
        return False, f"FAIL — script not found: {abs_path}"

    try:
        result = subprocess.run(
            [sys.executable, abs_path],
            input=tc.input,
            capture_output=True,
            text=True,
            timeout=tc.timeout,
        )
    except subprocess.TimeoutExpired:
        return False, f"FAIL — timed out after {tc.timeout}s"

    actual = _normalize(result.stdout)
    expected = _resolve_expected(tc)

    if actual == expected:
        return True, "PASS"

    lines = [
        "FAIL",
        f"    expected : {repr(expected)}",
        f"    actual   : {repr(actual)}",
    ]
    if result.returncode != 0:
        lines.append(f"    exit code: {result.returncode}")
    if result.stderr.strip():
        lines.append(f"    stderr   : {result.stderr.strip()}")
    return False, "\n".join(lines)


# ---------------------------------------------------------------------------
# TEST REGISTRY — add your scripts here
# ---------------------------------------------------------------------------

TEST_REGISTRY: List[Tuple[str, List[TestCase]]] = [
    # Example — delete or replace with your own scripts:
    # ("src/hello.py", [
    #     TestCase("prints greeting", "", "Hello, World!"),
    # ]),
]


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def run_all_tests() -> bool:
    if not TEST_REGISTRY:
        print("No tests registered. Add entries to TEST_REGISTRY in tests/test_runner.py")
        return True

    total = passed = 0
    failed_scripts: List[str] = []
    width = 54

    for script_path, cases in TEST_REGISTRY:
        script_pass = script_fail = 0
        print(f"\n{'=' * width}")
        print(f"  {script_path}")
        print(f"{'=' * width}")

        for tc in cases:
            total += 1
            ok, msg = run_test(script_path, tc)
            icon = "✓" if ok else "✗"
            print(f"  {icon} {tc.description}")
            if not ok:
                print(f"    {msg}")
                script_fail += 1
            else:
                passed += 1
                script_pass += 1

        summary = f"  {script_pass}/{script_pass + script_fail} passed"
        if script_fail:
            failed_scripts.append(script_path)
            summary += "  ← FAILURES"
        print(summary)

    print(f"\n{'=' * width}")
    print(f"  TOTAL: {passed}/{total} tests passed")
    if failed_scripts:
        print("  Scripts with failures:")
        for name in failed_scripts:
            print(f"    • {name}")
    else:
        print("  All tests passed! 🎉")
    print(f"{'=' * width}\n")
    return passed == total


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
