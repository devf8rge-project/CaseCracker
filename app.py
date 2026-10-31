"""CaseCracker frontend. Execution and AI live in separate modules."""
from pathlib import Path
import base64
import uuid

import streamlit as st

from casecracker.ai import suggest_test
from casecracker.editor import render_editor
from casecracker.edge_cases import generate_boundary_test_cases
from casecracker.examples import DEMO_EXAMPLE
from casecracker.execution import (
    extract_test_cases_from_problem,
    find_failing_test,
    find_first_failing_test,
    run_all_tests,
)
from casecracker.intro import render_intro
from casecracker.models import TestCase, TestSuggestion, SearchResult
from casecracker.runner import is_sandbox_available
from casecracker.settings import runner_status
from casecracker.owner_ui import render_owner_page
from casecracker.samples import sample_result
from casecracker.ui import render_results
from casecracker.proof_ui import analyze_reference, render_proof_tools


def load_example():
    problem, code = DEMO_EXAMPLE
    st.session_state.update(problem=problem, code=code, preview=False)
    st.session_state.editor_revision = st.session_state.get("editor_revision", 0) + 1
    st.session_state.test_cases = [
        {
            "id": "tc_demo_1",
            "name": "Test 1: Example from problem",
            "input": "3\n-2 0 5",
            "expected_output": "3",
            "explanation": "Illustrative case where negative numbers must be summed.",
        },
        {
            "id": "tc_demo_2",
            "name": "Test 2: All positive integers",
            "input": "4\n1 2 3 4",
            "expected_output": "10",
            "explanation": "Standard positive summation.",
        },
        {
            "id": "tc_demo_3",
            "name": "Test 3: Zero and negative values",
            "input": "3\n-5 0 -2",
            "expected_output": "-7",
            "explanation": "Sum with no positive integers.",
        },
    ]
    st.session_state.pop("result", None)
    for key in ("proof_bundle", "verified_patch", "blind_guess"):
        st.session_state.pop(key, None)


def clear_workspace():
    st.session_state.cleared_workspace = {
        key: st.session_state.get(key, "")
        for key in ("problem", "code")
    }
    st.session_state.cleared_test_cases = list(st.session_state.get("test_cases", []))
    st.session_state.update(problem="", code="", preview=False)
    st.session_state.editor_revision = st.session_state.get("editor_revision", 0) + 1
    st.session_state.test_cases = [
        {
            "id": "tc_default",
            "name": "Test 1",
            "input": "",
            "expected_output": "",
            "explanation": "",
        }
    ]
    st.session_state.pop("result", None)
    for key in ("proof_bundle", "verified_patch", "blind_guess"):
        st.session_state.pop(key, None)


def undo_clear():
    if "cleared_workspace" in st.session_state:
        st.session_state.update(st.session_state.pop("cleared_workspace"))
    if "cleared_test_cases" in st.session_state:
        st.session_state.test_cases = st.session_state.pop("cleared_test_cases")
    st.session_state.editor_revision = st.session_state.get("editor_revision", 0) + 1


def load_proof_demo():
    reference = "n = int(input())\nvalues = list(map(int, input().split()))\nassert n >= 1 and len(values) == n\ntotal = 0\nfor value in values:\n    total += value\nprint(total)\n"
    st.session_state.update(
        problem="Read n integers and print their sum. n >= 1; negative values are valid.",
        code=reference.replace("total += value", "total += max(value, 0)"),
        reference_code=reference, custom_input="6\n8 -9 4 -2 7 0",
        regression_inputs='["1\\n0", "3\\n1 2 3", "2\\n-1 -2"]', preview=False,
    )
    st.session_state.test_cases = [{"id": "proof_" + uuid.uuid4().hex[:6], "name": "Proof counterexample", "input": "6\n8 -9 4 -2 7 0", "expected_output": "", "explanation": "Compared against reference."}]
    st.session_state.editor_revision = st.session_state.get("editor_revision", 0) + 1
    for key in ("result", "proof_bundle", "verified_patch", "blind_guess"):
        st.session_state.pop(key, None)


st.set_page_config(page_title="CaseCracker · Find your edge case", page_icon="🔎", layout="wide")

if st.query_params.get("view") == "owner":
    render_owner_page()
    st.stop()


def remember_appearance():
    st.query_params["theme"] = st.session_state.color_mode.lower()


if "color_mode" not in st.session_state:
    st.session_state.color_mode = (
        "Light" if st.query_params.get("theme", "dark").lower() == "light" else "Dark"
    )
st.radio("Appearance", ["Dark", "Light"], horizontal=True, key="color_mode", on_change=remember_appearance)
st.html(f"<style>{(Path(__file__).parent / 'assets/style.css').read_text()}</style>")
if st.session_state.color_mode == "Light":
    st.html(f"<style>{(Path(__file__).parent / 'assets/light.css').read_text()}</style>")

logo_data = base64.b64encode((Path(__file__).parent / "assets/logo.svg").read_bytes()).decode("ascii")
services = runner_status()
sandbox_active = services['backend'] == 'local' and is_sandbox_available()

if services['remote']:
    runner_badge = '<div class="preview-banner"><strong>HOSTED SANDBOX</strong><span>' + (
        'Configured. Each execution uses a fresh, network-disabled VM.' if services['configured'] else
        'Code execution is temporarily unavailable. Please try again later.') + '</span></div>'
else:
    runner_badge = '<div class="preview-banner"><strong>LOCAL DEVELOPMENT</strong><span>Local process runner; do not use this backend for untrusted public submissions.</span></div>'

st.markdown(f'''<nav class="topbar" aria-label="Main navigation">
<a class="brand" href="#home"><img class="brand-logo" src="data:image/svg+xml;base64,{logo_data}" alt="" width="38" height="38"> CaseCracker<span class="beta">{"SANDBOX" if sandbox_active else "RUNNER"}</span></a>
<div class="nav-links"><a href="#workspace">Workspace</a><a href="#guide">How it works ↗</a>
<a href="https://github.com/devf8rge-project/CaseCracker" target="_blank" rel="noopener noreferrer">GitHub ↗</a></div></nav>
<section class="hero" id="home"><div class="eyebrow"><span class="dot"></span> A WORKSPACE FOR THE WHAT-IFS</div>
<h1>Find the case<br>you <span>didn’t consider.</span></h1>
<p>One problem. One solution. A closer look at the boundaries.<br>Put your Python code to the test.</p>
<a class="workspace-link" href="#workspace">Open workspace <span>↗</span></a><div class="hero-tags"><span>01 / Describe</span><span>02 / Add code</span><span>03 / Inspect</span></div></section>
{runner_badge}
<div id="workspace" class="workspace-heading"><div><span class="eyebrow">THE WORKBENCH</span><h2>Your next test starts here.</h2></div><span class="language-tag">Python 3</span></div>''', unsafe_allow_html=True)

# Initialize test cases in session state
if "test_cases" not in st.session_state:
    st.session_state.test_cases = [
        {
            "id": "tc_1",
            "name": "Test 1: Example",
            "input": "3\n-2 0 5",
            "expected_output": "3",
            "explanation": "Illustrative case with negative and zero integers",
        }
    ]

expanded = st.toggle("Expand workspace", key="expanded_workspace", help="Use the full page width and a taller editor. Results move below the workspace.")
if expanded:
    workspace, results = st.container(), st.container()
else:
    workspace, results = st.columns([1.2, 1], gap="large")

with workspace:
    toolbar_label, example_action, clear_action = st.columns([2, 1.3, 1])
    with toolbar_label:
        st.markdown('<div class="panel-label">01 &nbsp; / &nbsp; YOUR SOLUTION</div>', unsafe_allow_html=True)
    with example_action:
        st.button("Load example", on_click=load_example, use_container_width=True)
    with clear_action:
        st.button("Clear", on_click=clear_workspace, use_container_width=True, help="Clears the current problem, code, and results.")
    if st.session_state.get("cleared_workspace"):
        st.button("Undo clear", on_click=undo_clear, help="Restore the problem and code you just cleared.")

    with st.container(border=True):
        st.text_area("Problem statement", key="problem", height=180, placeholder="What should the program do? Include input/output format, constraints, and examples.", help="Include boundary values and the expected behavior for unusual inputs.")
        render_editor()

        # Multiple Test Cases Expander
        with st.expander(f"Test cases ({len(st.session_state.test_cases)})", expanded=True):
            st.markdown(
                '<p style="font-size: 0.82rem; color: #94a3b8; margin-bottom: 0.75rem;">'
                '<strong>Execution Contract:</strong> Your code can read standard input via <code>input()</code> or '
                '<code>sys.stdin.read()</code> and print to stdout, <em>or</em> define <code>def solve(input_data): return ...</code>. '
                'Both modes are executed independently in isolated sandboxes.'
                '</p>',
                unsafe_allow_html=True,
            )

            tool_c1, tool_c2, tool_c3 = st.columns([1.2, 1.5, 1.5])
            with tool_c1:
                if st.button("➕ Add test", key="btn_add_test", use_container_width=True):
                    next_idx = len(st.session_state.test_cases) + 1
                    st.session_state.test_cases.append({
                        "id": f"tc_{uuid.uuid4().hex[:6]}",
                        "name": f"Test {next_idx}",
                        "input": "",
                        "expected_output": "",
                        "explanation": "",
                    })
                    st.rerun()

            with tool_c2:
                if st.button("📋 Extract problem cases", key="btn_extract_cases", use_container_width=True):
                    extracted = extract_test_cases_from_problem(st.session_state.get("problem", ""))
                    if extracted:
                        st.session_state.test_cases = [tc.to_dict() for tc in extracted]
                        st.toast(f"Extracted {len(extracted)} test cases from problem statement!", icon="📋")
                        st.rerun()
                    else:
                        st.toast("No 'Input:' and 'Output:' examples detected in problem statement.", icon="⚠️")

            with tool_c3:
                if st.button("⚡ Suggest edge cases", key="btn_suggest_edges", use_container_width=True):
                    boundary_cases = generate_boundary_test_cases(st.session_state.get("problem", ""))
                    st.session_state.test_cases.extend([bc.to_dict() for bc in boundary_cases])
                    st.toast(f"Added {len(boundary_cases)} boundary edge cases to test suite!", icon="⚡")
                    st.rerun()

            # Render each test case editor
            to_delete_idx = None
            for idx, tc in enumerate(st.session_state.test_cases):
                with st.container(border=True):
                    row1_col1, row1_col2 = st.columns([4.2, 0.8])
                    with row1_col1:
                        tc["name"] = st.text_input(
                            f"Test {idx + 1} Name",
                            value=tc.get("name", f"Test {idx + 1}"),
                            key=f"tc_name_{tc['id']}_{idx}",
                            label_visibility="collapsed",
                            placeholder=f"Test {idx + 1} Name",
                        )
                    with row1_col2:
                        if st.button("🗑️", key=f"del_tc_{tc['id']}_{idx}", help="Remove this test case"):
                            to_delete_idx = idx

                    in_col, out_col = st.columns(2)
                    with in_col:
                        tc["input"] = st.text_area(
                            "Input (stdin / argument)",
                            value=tc.get("input", ""),
                            key=f"tc_input_{tc['id']}_{idx}",
                            height=75,
                            placeholder="Input data for this test case",
                        )
                    with out_col:
                        tc["expected_output"] = st.text_area(
                            "Expected Output",
                            value=tc.get("expected_output", ""),
                            key=f"tc_exp_{tc['id']}_{idx}",
                            height=75,
                            placeholder="Expected stdout to verify against",
                        )

                    tc["explanation"] = st.text_input(
                        "Explanation (optional)",
                        value=tc.get("explanation", ""),
                        key=f"tc_expl_{tc['id']}_{idx}",
                        placeholder="Optional description of this test scenario",
                    )

            if to_delete_idx is not None and len(st.session_state.test_cases) > 1:
                st.session_state.test_cases.pop(to_delete_idx)
                st.rerun()
            elif to_delete_idx is not None and len(st.session_state.test_cases) == 1:
                st.toast("Keep at least one test case in your suite.", icon="ℹ️")

        with st.expander("Execution proof · reference solution & regression tests"):
            st.caption("Supply a trusted reference to enable automatic shrinking, traces, and optional AI patch verification. Reference code must reject inputs outside the problem constraints.")
            st.button("Load execution demo", on_click=load_proof_demo)
            st.text_area("Trusted reference Python code", key="reference_code", height=220)
            st.text_area("Regression inputs (JSON array of stdin strings)", key="regression_inputs", height=90,
                         placeholder='["3\\n1 2 3", "1\\n-1"]')
            st.caption("AI analysis is optional and runs only when you request it.")

        st.checkbox("Show temporary sample results (illustration only)", key="preview", help="Displays fixed demo data, not a test of your code.")

        btn_c1, btn_c2 = st.columns(2)
        with btn_c1:
            run_all_submitted = st.button("▶ Run all tests", type="primary", use_container_width=True)
        with btn_c2:
            find_failing_submitted = st.button("🔎 Find failing test", use_container_width=True)

        st.caption("Execution uses disposable hosted VMs." if services["remote"] else "Local development runner; not suitable for untrusted public code.")

    if (run_all_submitted or find_failing_submitted) and not st.session_state.preview and not services['configured']:
        st.error("Code execution is temporarily unavailable. No submitted code was executed. Please contact the app owner.")
        run_all_submitted = find_failing_submitted = False

    if run_all_submitted or find_failing_submitted:
        for key in ("proof_bundle", "verified_patch", "blind_guess"):
            st.session_state.pop(key, None)
        if st.session_state.get("reference_code", "").strip() and not st.session_state.preview:
            run_all_submitted = find_failing_submitted = False
            st.session_state.pop("result", None)
            try:
                code_val = st.session_state.get("code", "").strip()
                if not code_val:
                    raise ValueError("Add your Python code to continue.")
                with st.spinner("Comparing, shrinking, and recording bounded traces…"):
                    result, bundle = analyze_reference(
                        st.session_state.get("problem", "").strip(), code_val,
                        st.session_state.reference_code.strip(), "",
                        st.session_state.get("regression_inputs", ""),
                        suite_inputs=[tc.get("input", "") for tc in st.session_state.test_cases])
                st.session_state.result, st.session_state.proof_bundle = result, bundle
            except Exception as exc:
                st.error(f"Reference analysis unavailable: {exc}")

    if run_all_submitted:
        st.session_state.pop("result", None)
        code_val = st.session_state.get("code", "").strip()
        if not code_val:
            st.warning("Add your Python code to test.")
        elif st.session_state.preview:
            st.session_state.result = sample_result()
        else:
            test_case_objs = [
                TestCase.from_dict(d)
                for d in st.session_state.test_cases
                if d.get("name") or d.get("input")
            ]
            with st.spinner("Running all tests in secure sandbox…"):
                suite_res = run_all_tests(code_val, test_case_objs)
            all_passed = suite_res.passed_count == suite_res.total_tests and suite_res.total_tests > 0

            if suite_res.syntax_error:
                msg = f"Syntax error: {suite_res.syntax_error}"
            elif all_passed:
                msg = f"🟢 All {suite_res.total_tests} test cases passed!"
            else:
                msg = (
                    f"Test run completed: {suite_res.passed_count}/{suite_res.total_tests} passed, "
                    f"{suite_res.failed_count} failed, {suite_res.error_count} errors, {suite_res.timeout_count} timed out."
                )

            st.session_state.result = SearchResult(
                executed=True,
                passed=all_passed,
                message=msg,
                execution_time_ms=suite_res.total_duration_ms,
                sandboxed=suite_res.sandboxed,
                suite_result=suite_res,
            )

    if find_failing_submitted:
        st.session_state.pop("result", None)
        code_val = st.session_state.get("code", "").strip()
        if not code_val:
            st.warning("Add your Python code to test.")
        elif st.session_state.preview:
            st.session_state.result = sample_result()
        else:
            test_case_objs = [
                TestCase.from_dict(d)
                for d in st.session_state.test_cases
                if d.get("name") or d.get("input")
            ]
            with st.spinner("Searching for failing test…"):
                st.session_state.result = find_first_failing_test(code_val, test_case_objs)

with results:
    st.markdown('<div class="panel-label results-label">02 &nbsp; / &nbsp; TEST INSIGHTS</div>', unsafe_allow_html=True)
    render_results(st.session_state.get("result"))

    with st.container(border=True):
        st.markdown("**Look beyond the happy path**")
        st.caption("Good edge cases start at the boundaries of the problem’s valid inputs.")
        st.markdown('<div class="edge-tags"><span>Minimum size</span><span>Repeated values</span><span>Zero & negatives</span><span>Upper limits</span></div>', unsafe_allow_html=True)

render_proof_tools()

st.markdown(f'''<section id="guide" class="guide"><div class="eyebrow">KEEP IT SIMPLE</div><h2>Three steps. Nothing extra.</h2><div class="guide-grid">
<article><span>01</span><h3>Set the scene</h3><p>Describe the goal, constraints, and exactly what a correct answer looks like.</p></article>
<article><span>02</span><h3>Bring your logic</h3><p>Paste a complete Python script or solve(input_data) function. Load the example to explore.</p></article>
<article><span>03</span><h3>Read the evidence</h3><p>Inspect verified results from the sandboxed runner or explore sample edge cases.</p></article>
</div></section><footer><div class="brand"><img class="brand-logo" src="data:image/svg+xml;base64,{logo_data}" alt="" width="32" height="32"> CaseCracker</div><span>Stay curious. Check the boundaries.</span><span>Execution status shown above</span></footer>''', unsafe_allow_html=True)

# Mount after the page so the real workspace is visible behind the blur.
render_intro()
