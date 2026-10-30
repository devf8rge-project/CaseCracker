"""CaseCracker frontend. Execution and AI live in separate modules."""
from pathlib import Path
import base64

import streamlit as st

from casecracker.ai import suggest_test
from casecracker.editor import render_editor
from casecracker.examples import DEMO_EXAMPLE
from casecracker.execution import find_failing_test
from casecracker.intro import render_intro
from casecracker.models import TestSuggestion
from casecracker.runner import is_sandbox_available
from casecracker.samples import sample_result
from casecracker.ui import render_results


def load_example():
    problem, code = DEMO_EXAMPLE
    st.session_state.update(problem=problem, code=code, preview=True)
    st.session_state.editor_revision = st.session_state.get("editor_revision", 0) + 1
    st.session_state.pop("result", None)


def clear_workspace():
    st.session_state.cleared_workspace = {key: st.session_state.get(key, "") for key in ("problem", "code", "custom_input", "custom_expected")}
    st.session_state.update(problem="", code="", preview=False, custom_input="", custom_expected="")
    st.session_state.editor_revision = st.session_state.get("editor_revision", 0) + 1
    st.session_state.pop("result", None)


def undo_clear():
    st.session_state.update(st.session_state.pop("cleared_workspace", {}))
    st.session_state.editor_revision = st.session_state.get("editor_revision", 0) + 1


st.set_page_config(page_title="CaseCracker · Find your edge case", page_icon="🔎", layout="wide")

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
sandbox_active = is_sandbox_available()

runner_badge = (
    '<div class="preview-banner runner-active"><strong>SECURE RUNNER ACTIVE</strong>'
    '<span>macOS Seatbelt sandbox enabled with network isolation, resource bounds, and execution timeouts.</span></div>'
    if sandbox_active
    else '<div class="preview-banner"><strong>LOCAL RUNNER ACTIVE</strong>'
    '<span>Subprocess execution with resource limits and timeouts.</span></div>'
)

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
        st.text_area("Problem statement", key="problem", height=190, placeholder="What should the program do? Include input/output format, constraints, and examples.", help="Include boundary values and the expected behavior for unusual inputs.")
        render_editor()

        with st.expander("Custom test case (optional)", expanded=False):
            st.text_area(
                "Test input (stdin)",
                key="custom_input",
                height=80,
                placeholder="e.g. 5\n1 2 3 4 5",
                help="Input passed to your program's stdin.",
            )
            st.text_area(
                "Expected output (optional)",
                key="custom_expected",
                height=60,
                placeholder="e.g. 15",
                help="Expected output to verify against your program's stdout.",
            )

        st.checkbox("Show temporary sample results (illustration only)", key="preview", help="Displays fixed demo data, not a test of your code.")
        submitted = st.button("Find failing test →", type="primary", use_container_width=True)
        st.caption("Sample mode shows illustrative data." if st.session_state.get("preview") else ("Network and filesystem isolation enabled on this host." if sandbox_active else "Process limits enabled. Network and filesystem sandboxing unavailable on this host."))

    if submitted:
        st.session_state.pop("result", None)
        problem_val = st.session_state.get("problem", "").strip()
        code_val = st.session_state.get("code", "").strip()
        custom_in = st.session_state.get("custom_input", "").strip()
        custom_exp = st.session_state.get("custom_expected", "").strip()

        if not problem_val and not custom_in:
            st.warning("Add a problem statement or custom test case to continue.")
        elif not code_val:
            st.warning("Add your Python code to continue.")
        elif st.session_state.preview:
            st.session_state.result = sample_result()
        else:
            if custom_in:
                suggestion = TestSuggestion(
                    connected=True,
                    message="User custom test case",
                    test_input=custom_in,
                    expected_output=custom_exp if custom_exp else None,
                )
            else:
                suggestion = suggest_test(problem_val, code_val)
            with st.spinner("Checking your test…"):
                st.session_state.result = find_failing_test(problem_val, code_val, suggestion)

with results:
    st.markdown('<div class="panel-label results-label">02 &nbsp; / &nbsp; TEST INSIGHTS</div>', unsafe_allow_html=True)
    render_results(st.session_state.get("result"))

    with st.container(border=True):
        st.markdown("**Look beyond the happy path**")
        st.caption("Good edge cases start at the boundaries of the problem’s valid inputs.")
        st.markdown('<div class="edge-tags"><span>Minimum size</span><span>Repeated values</span><span>Zero & negatives</span><span>Upper limits</span></div>', unsafe_allow_html=True)

st.markdown(f'''<section id="guide" class="guide"><div class="eyebrow">KEEP IT SIMPLE</div><h2>Three steps. Nothing extra.</h2><div class="guide-grid">
<article><span>01</span><h3>Set the scene</h3><p>Describe the goal, constraints, and exactly what a correct answer looks like.</p></article>
<article><span>02</span><h3>Bring your logic</h3><p>Paste a complete Python script. Load the example to explore the interface.</p></article>
<article><span>03</span><h3>Read the evidence</h3><p>Compare the reported output with your expected answer. Sample results are always labeled.</p></article>
</div></section><footer><div class="brand"><img class="brand-logo" src="data:image/svg+xml;base64,{logo_data}" alt="" width="32" height="32"> CaseCracker</div><span>Stay curious. Check the boundaries.</span><span>Python workspace · CaseCracker</span></footer>''', unsafe_allow_html=True)

# Mount after the page so the real workspace is visible behind the blur.
render_intro()
