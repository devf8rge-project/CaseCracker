"""Heuristic boundary and edge case generation based on algorithmic problem patterns."""

from __future__ import annotations

import re
import uuid
from casecracker.models import TestCase


def generate_boundary_test_cases(problem: str = "") -> list[TestCase]:
    """Generate boundary and edge cases tailored to algorithmic boundaries.

    Generated cases include:
    - Empty input
    - Minimum and zero values
    - Negative values
    - Single element
    - Duplicate values
    - Large / upper limit values

    Note: As per requirements, generated boundary cases have empty expected outputs
    until verified or filled in by the user or an AI oracle.
    """
    cases: list[TestCase] = []

    # 1. Zero values
    cases.append(
        TestCase(
            id=str(uuid.uuid4())[:8],
            name="Edge: Zero value",
            input="0",
            expected_output="",
            explanation="Tests behavior when input contains or equals zero.",
            is_generated=True,
        )
    )

    # 2. Negative numbers
    cases.append(
        TestCase(
            id=str(uuid.uuid4())[:8],
            name="Edge: Negative integers",
            input="-1 -5 -10",
            expected_output="",
            explanation="Tests whether negative numbers are preserved or handled properly.",
            is_generated=True,
        )
    )

    # 3. Single element
    cases.append(
        TestCase(
            id=str(uuid.uuid4())[:8],
            name="Edge: Single element",
            input="1",
            expected_output="",
            explanation="Tests the minimum non-empty collection/element boundary.",
            is_generated=True,
        )
    )

    # 4. Duplicate values
    cases.append(
        TestCase(
            id=str(uuid.uuid4())[:8],
            name="Edge: Duplicate values",
            input="3\n5 5 5",
            expected_output="",
            explanation="Tests sequences containing identical duplicate values.",
            is_generated=True,
        )
    )

    # 5. Empty input
    cases.append(
        TestCase(
            id=str(uuid.uuid4())[:8],
            name="Edge: Empty input",
            input="",
            expected_output="",
            explanation="Tests handling of empty, whitespace, or EOF input.",
            is_generated=True,
        )
    )

    # 6. Check for constraints in problem text (e.g. 10^5, 100000, 1000)
    max_val = "100000"
    if problem:
        matches = re.findall(r"(?:<=|<|limit|max)\s*(\d{2,10})", problem, re.IGNORECASE)
        if matches:
            max_val = matches[-1]

    cases.append(
        TestCase(
            id=str(uuid.uuid4())[:8],
            name="Edge: Upper constraint limit",
            input=max_val,
            expected_output="",
            explanation=f"Tests performance and boundary limits up to {max_val}.",
            is_generated=True,
        )
    )

    return cases
