from __future__ import annotations

from dataclasses import dataclass


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
