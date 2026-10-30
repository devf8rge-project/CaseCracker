"""Data models for CaseCracker test execution and reporting."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class TestStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    ERROR = "ERROR"
    TIMEOUT = "TIMEOUT"
    UNVERIFIED = "UNVERIFIED"


@dataclass
class TestCase:
    id: str
    name: str
    input: str
    expected_output: str = ""
    explanation: str = ""
    is_generated: bool = False

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "input": self.input,
            "expected_output": self.expected_output,
            "explanation": self.explanation,
            "is_generated": self.is_generated,
        }

    @classmethod
    def from_dict(cls, data: dict) -> TestCase:
        return cls(
            id=data.get("id", ""),
            name=data.get("name", "Test case"),
            input=data.get("input", ""),
            expected_output=data.get("expected_output", ""),
            explanation=data.get("explanation", ""),
            is_generated=data.get("is_generated", False),
        )


@dataclass
class TestResult:
    test_case: TestCase
    status: TestStatus
    actual_output: str
    execution_time_ms: float
    stderr: str = ""
    error_message: str | None = None
    error_traceback: str | None = None
    comparison_rule: str | None = None
    diff: str | None = None
    sandboxed: bool = False

    def to_dict(self) -> dict:
        return {
            "test_case": self.test_case.to_dict(),
            "status": self.status.value,
            "actual_output": self.actual_output,
            "execution_time_ms": self.execution_time_ms,
            "stderr": self.stderr,
            "error_message": self.error_message,
            "error_traceback": self.error_traceback,
            "comparison_rule": self.comparison_rule,
            "diff": self.diff,
            "sandboxed": self.sandboxed,
        }


@dataclass
class TestSuiteResult:
    results: list[TestResult] = field(default_factory=list)
    total_tests: int = 0
    passed_count: int = 0
    failed_count: int = 0
    error_count: int = 0
    timeout_count: int = 0
    unverified_count: int = 0
    total_duration_ms: float = 0.0
    syntax_error: str | None = None
    syntax_error_line: int | None = None
    sandboxed: bool = False

    def to_dict(self) -> dict:
        return {
            "total_tests": self.total_tests,
            "passed_count": self.passed_count,
            "failed_count": self.failed_count,
            "error_count": self.error_count,
            "timeout_count": self.timeout_count,
            "unverified_count": self.unverified_count,
            "total_duration_ms": self.total_duration_ms,
            "syntax_error": self.syntax_error,
            "syntax_error_line": self.syntax_error_line,
            "sandboxed": self.sandboxed,
            "results": [r.to_dict() for r in self.results],
        }


@dataclass(frozen=True)
class TestSuggestion:
    connected: bool
    message: str
    test_input: str | None = None
    expected_output: str | None = None


@dataclass(frozen=True)
class SearchResult:
    executed: bool
    message: str
    is_sample: bool = False
    test_input: str | None = None
    expected_output: str | None = None
    actual_output: str | None = None
    passed: bool | None = None
    execution_time_ms: float | None = None
    error: str | None = None
    sandboxed: bool = False
    suite_result: TestSuiteResult | None = None
    first_failing_case: TestResult | None = None
