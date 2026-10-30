"""Single illustrative frontend demo; loading it does not run code."""

DEMO_EXAMPLE = (
        "Read n integers and print their sum.\nInput: n, followed by n space-separated integers.\nConstraints: 1 ≤ n ≤ 100000; values may be negative.\nExample input:\n3\n-2 0 5\nExpected output:\n3",
        "# Illustrative buggy solution: ignores negatives.\nn = int(input())\nvalues = list(map(int, input().split()))\nprint(sum(x for x in values if x > 0))\n",
)
