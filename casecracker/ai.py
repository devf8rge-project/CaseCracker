"""AI integration only; never executes submitted code."""

from casecracker.models import TestSuggestion


def suggest_test(problem: str, code: str) -> TestSuggestion:
    """Replace this stub with an AI provider when configured."""
    return TestSuggestion(
        connected=False,
        message="AI test generation is not connected. No test was generated.",
    )
