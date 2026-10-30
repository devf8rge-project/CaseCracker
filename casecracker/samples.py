"""Explicitly synthetic examples for previewing the results panel."""

from casecracker.models import SearchResult


def sample_result() -> SearchResult:
    return SearchResult(
        executed=False,
        is_sample=True,
        message="Example only: for a task asking for the sum of integers, a "
        "hypothetical solution that ignores negative values would fail this case.",
        test_input="3\n-2 0 5",
        expected_output="3",
        actual_output="5",
    )
