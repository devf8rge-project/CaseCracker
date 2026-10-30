"""Frontend practice prompts. Loading an example does not run code."""

EXAMPLES = {
    "Arrays · Sum of integers": (
        "Read n integers and print their sum.\nInput: n, followed by n space-separated integers.\nConstraints: 1 ≤ n ≤ 100000; values may be negative.\nExample input:\n3\n-2 0 5\nExpected output:\n3",
        "# Illustrative buggy solution: ignores negatives.\nn = int(input())\nvalues = list(map(int, input().split()))\nprint(sum(x for x in values if x > 0))\n",
    ),
    "Strings · Palindrome": (
        "Read one nonempty lowercase string and print YES if it is a palindrome, otherwise NO.\nConstraints: 1 ≤ length ≤ 100000.\nExample input: radar\nExpected output: YES",
        "# Write your solution here.\ntext = input().strip()\n",
    ),
    "Sorting · Second distinct maximum": (
        "Read n integers. Print the second largest distinct value, or NONE if it does not exist.\nInput: n, then n space-separated integers.\nConstraints: 1 ≤ n ≤ 100000.\nExample input:\n4\n9 9 3 1\nExpected output:\n3",
        "# Write your solution here.\nn = int(input())\nvalues = list(map(int, input().split()))\n",
    ),
}
