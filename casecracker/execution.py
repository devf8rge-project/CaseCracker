"""Runner integration only, separate from the UI and AI provider."""

from casecracker.models import SearchResult, TestSuggestion


def find_failing_test(
    problem: str, code: str, suggestion: TestSuggestion
) -> SearchResult:
    """Integration stub. Connect an isolated runner before reporting execution.

    A real implementation must enforce resource limits and isolation, capture
    actual output, and verify it against an expected answer before claiming a
    failing test. This stub deliberately does not use exec or subprocess.
    """
    return SearchResult(
        executed=False,
        message=f"{suggestion.message} The execution runner is not connected. "
        "No failing test has been verified.",
    )
