"""Presentation layer for CaseCracker test results and execution insights."""

from __future__ import annotations

import json
from html import escape
import streamlit as st

from casecracker.models import SearchResult, TestResult, TestStatus, TestSuiteResult


_STATUS_BADGES = {
    TestStatus.PASS: (
        '<span style="background-color: rgba(16, 185, 129, 0.18); color: #10b981; '
        'border: 1px solid #10b981; padding: 2px 10px; border-radius: 9999px; '
        'font-size: 0.75rem; font-weight: 700; letter-spacing: 0.05em;">PASS</span>'
    ),
    TestStatus.FAIL: (
        '<span style="background-color: rgba(239, 68, 68, 0.18); color: #ef4444; '
        'border: 1px solid #ef4444; padding: 2px 10px; border-radius: 9999px; '
        'font-size: 0.75rem; font-weight: 700; letter-spacing: 0.05em;">FAIL</span>'
    ),
    TestStatus.ERROR: (
        '<span style="background-color: rgba(245, 158, 11, 0.18); color: #f59e0b; '
        'border: 1px solid #f59e0b; padding: 2px 10px; border-radius: 9999px; '
        'font-size: 0.75rem; font-weight: 700; letter-spacing: 0.05em;">ERROR</span>'
    ),
    TestStatus.TIMEOUT: (
        '<span style="background-color: rgba(168, 85, 247, 0.18); color: #c084fc; '
        'border: 1px solid #a855f7; padding: 2px 10px; border-radius: 9999px; '
        'font-size: 0.75rem; font-weight: 700; letter-spacing: 0.05em;">TIMEOUT</span>'
    ),
    TestStatus.UNVERIFIED: (
        '<span style="background-color: rgba(59, 130, 246, 0.18); color: #60a5fa; '
        'border: 1px solid #3b82f6; padding: 2px 10px; border-radius: 9999px; '
        'font-size: 0.75rem; font-weight: 700; letter-spacing: 0.05em;">UNVERIFIED</span>'
    ),
}


def _render_test_card(test_res: TestResult, index: int, default_expanded: bool = False) -> None:
    """Render an individual test result in an expandable card."""
    badge = _STATUS_BADGES.get(test_res.status, test_res.status.value)
    title = f"{test_res.test_case.name} ({test_res.execution_time_ms:.1f} ms)"

    with st.expander(f"{test_res.status.value} · {title}", expanded=default_expanded):
        st.markdown(
            f'<div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 0.75rem;">'
            f'<div><strong>{escape(test_res.test_case.name)}</strong></div>'
            f'<div>{badge} &nbsp; <span style="color: #94a3b8; font-size: 0.8rem;">⏱️ {test_res.execution_time_ms:.1f} ms</span></div>'
            f'</div>',
            unsafe_allow_html=True,
        )

        if test_res.test_case.explanation:
            st.caption(f"💡 {test_res.test_case.explanation}")

        # Test Input
        st.markdown("**Test Input (stdin / argument)**")
        st.code(test_res.test_case.input if test_res.test_case.input else "(empty input)", language="text")

        # Expected vs Actual
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**Expected Output**")
            if test_res.test_case.expected_output:
                st.code(test_res.test_case.expected_output, language="text")
            else:
                st.caption("No expected output provided (exploratory case).")

        with col2:
            st.markdown("**Runner Output**")
            if test_res.status == TestStatus.TIMEOUT:
                st.warning("⚠️ Time Limit Exceeded (> 2.0s). Execution killed by timeout watchdog.")
            elif test_res.actual_output:
                st.code(test_res.actual_output, language="text")
            elif test_res.status == TestStatus.ERROR:
                st.caption("No output produced prior to exception.")
            else:
                st.code("(empty output)", language="text")

        # Output comparison or diff if failure
        if test_res.status == TestStatus.FAIL:
            if test_res.comparison_rule:
                st.caption(f"Comparison: {test_res.comparison_rule}")
            if test_res.diff:
                st.markdown("**Output Differences (− Expected, + Actual)**")
                st.code(test_res.diff, language="diff")

        elif test_res.status == TestStatus.PASS:
            rule = test_res.comparison_rule or "Matched"
            st.success(f"✓ Matched via {rule}")

        elif test_res.status == TestStatus.ERROR:
            st.error(f"💥 {test_res.error_message or 'Runtime Error'}")
            if test_res.error_traceback:
                st.markdown("**Error Details & Traceback**")
                st.code(test_res.error_traceback, language="python")

        elif test_res.status == TestStatus.TIMEOUT:
            st.error("⏳ Solution exceeded the maximum time limit. Check for infinite loops or non-terminating recursion.")

        elif test_res.status == TestStatus.UNVERIFIED:
            st.info("ℹ️ Code executed without errors. Provide an expected output above to verify correctness.")


def _render_suite_summary(suite: TestSuiteResult) -> None:
    """Render top-level summary metrics for a test suite run."""
    counts = [('Total', suite.total_tests), ('Passed', suite.passed_count),
              ('Failed', suite.failed_count), ('Errors', suite.error_count),
              ('Timed out', suite.timeout_count), ('Unverified', suite.unverified_count)]
    cards = ''.join(f'<div class="stat"><span>{label}</span><strong>{value}</strong></div>' for label, value in counts)
    st.markdown(f'<div class="stat-grid">{cards}</div>', unsafe_allow_html=True)

    sandbox_label = "Isolated runner" if suite.sandboxed else "Local process limits"
    st.caption(
        f"⏱️ Total execution time: {suite.total_duration_ms:.1f} ms · "
        f"🔒 {sandbox_label} (See configured backend for isolation details)"
    )


def render_results(result: SearchResult | None) -> None:
    """Main presentation handler for test insights area."""
    with st.container(border=True):
        if result is None:
            st.markdown(
                '''<div class="empty-result"><div class="orbit"><span>⌕</span></div>
<div class="eyebrow">YOUR NEXT CLUE</div><h3>The evidence goes here.</h3>
<p>Add your code and a test case. We’ll show what happened, what was expected, and where to look next.</p>
<div class="empty-status">No tests executed yet</div></div>''',
                unsafe_allow_html=True,
            )
            return

        # Case 1: Temporary illustrative sample
        if result.is_sample:
            st.warning("TEMPORARY SAMPLE — illustrative demo only. No code was executed.")
            st.write(result.message)
            if result.test_input is not None:
                st.markdown("**Sample input**")
                st.code(result.test_input, language="text")
            exp_col, act_col = st.columns(2)
            with exp_col:
                st.markdown("**Sample expected output**")
                st.code(result.expected_output or "", language="text")
            with act_col:
                st.markdown("**Sample hypothetical output**")
                st.code(result.actual_output or "", language="text")
            return

        # Case 2: Syntax Error occurred before running
        suite = result.suite_result
        if suite and suite.syntax_error:
            st.error(f"🚨 **Syntax Error in Solution Code**")
            st.markdown(f"**Error text**: `{suite.syntax_error}`")
            if suite.syntax_error_line:
                st.caption(f"Check your code around line {suite.syntax_error_line}.")
            st.info("Fix the syntax error in the code editor to run test cases.")
            return

        # Case 3: Test suite executed
        if suite and suite.results:
            if result.first_failing_case:
                st.error(result.message)
            elif result.passed:
                st.success(result.message)
            else:
                st.info(result.message)

            _render_suite_summary(suite)

            tab_results, tab_json = st.tabs(["Test details", "Download result ↓"])

            with tab_results:
                # Render each test card
                for idx, t_res in enumerate(suite.results, start=1):
                    # Expand if it failed, crashed, or timed out, or if it's the only test
                    should_expand = (
                        t_res.status in (TestStatus.FAIL, TestStatus.ERROR, TestStatus.TIMEOUT)
                        or len(suite.results) == 1
                    )
                    _render_test_card(t_res, idx, default_expanded=should_expand)

            with tab_json:
                st.download_button(
                    "Download test results (JSON) ↓",
                    data=json.dumps(suite.to_dict(), indent=2),
                    file_name="casecracker-test-results.json",
                    mime="application/json",
                    use_container_width=True,
                )
            return

        # Fallback / Single case execution
        if not result.executed:
            st.info(result.message)
        else:
            if result.passed:
                st.success(result.message)
            else:
                st.error(result.message)

            if result.test_input is not None:
                st.markdown("**Test input**")
                st.code(result.test_input, language="text")
            c1, c2 = st.columns(2)
            with c1:
                st.markdown("**Expected output**")
                st.code(result.expected_output or "(none)", language="text")
            with c2:
                st.markdown("**Runner output**")
                st.code(result.actual_output or "(none)", language="text")

    st.caption("Results reflect your latest test execution. Tests run in fresh, isolated sandboxes.")
