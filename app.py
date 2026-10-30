"""CaseCracker frontend. Execution and AI live in separate modules."""
from pathlib import Path

import streamlit as st

from casecracker.ai import suggest_test
from casecracker.editor import render_editor
from casecracker.execution import find_failing_test
from casecracker.samples import sample_result
from casecracker.ui import render_results

EXAMPLE_PROBLEM = "Read n integers and print their sum.\n\nInput: n on the first line, followed by n space-separated integers.\nConstraints: 1 ≤ n ≤ 100000; -1000000 ≤ each integer ≤ 1000000.\nOutput: a single integer, the sum.\n\nExample input:\n3\n-2 0 5\n\nExample output:\n3"
EXAMPLE_CODE = "# Demo solution with an intentional bug: ignores negative numbers.\nn = int(input())\nvalues = list(map(int, input().split()))\nprint(sum(value for value in values if value > 0))\n"


def load_example():
    st.session_state.update(problem=EXAMPLE_PROBLEM, code=EXAMPLE_CODE, preview=True)
    st.session_state.editor_revision = st.session_state.get("editor_revision", 0) + 1
    st.session_state.pop("result", None)


def clear_workspace():
    st.session_state.update(problem="", code="", preview=False)
    st.session_state.editor_revision = st.session_state.get("editor_revision", 0) + 1
    st.session_state.pop("result", None)


st.set_page_config(page_title="CaseCracker · Find your edge case", page_icon="🔎", layout="wide")
st.markdown(f"<style>{(Path(__file__).parent / 'assets/style.css').read_text()}</style>", unsafe_allow_html=True)
st.markdown('''<nav class="topbar" aria-label="Main navigation">
<a class="brand" href="#home"><span class="brand-icon">⌘</span> CaseCracker<span class="beta">PREVIEW</span></a>
<div class="nav-links"><a href="#workspace">Workspace</a><a href="#guide">How it works ↗</a>
<a href="https://github.com/devf8rge-project/CaseCracker" target="_blank" rel="noopener noreferrer">GitHub ↗</a></div></nav>
<section class="hero" id="home"><div class="eyebrow"><span class="dot"></span> THE EDGE CASE WORKSPACE</div>
<h1>Every solution has<br>a <span>breaking point.</span></h1>
<p>A fresh perspective on your Python solution.<br>Bring the problem. Explore the boundaries. Find what you missed.</p>
<div class="hero-tags"><span>01 / Describe</span><span>02 / Add code</span><span>03 / Inspect</span></div></section>
<div class="preview-banner"><strong>INTERFACE PREVIEW</strong><span>AI and runner are not connected. Your code will not be executed.</span></div>
<div id="workspace" class="workspace-heading"><div><span class="eyebrow">THE WORKBENCH</span><h2>Challenge your assumptions.</h2></div><span class="language-tag">Python 3</span></div>''', unsafe_allow_html=True)

workspace, results = st.columns([1.2, 1], gap="large")
with workspace:
    toolbar_label, example_action, clear_action = st.columns([2, 1.3, 1])
    with toolbar_label:
        st.markdown('<div class="panel-label">01 &nbsp; / &nbsp; YOUR SOLUTION</div>', unsafe_allow_html=True)
    with example_action:
        st.button("Load example", on_click=load_example, use_container_width=True)
    with clear_action:
        st.button("Clear", on_click=clear_workspace, use_container_width=True)
    with st.container(border=True):
        st.text_area("Problem statement", key="problem", height=190, placeholder="What should the program do? Include input/output format, constraints, and examples.", help="Include boundary values and the expected behavior for unusual inputs.")
        render_editor()
        st.checkbox("Show temporary sample results (illustration only)", key="preview", help="Displays fixed demo data, not a test of your code.")
        submitted = st.button("Find failing test →", type="primary", use_container_width=True)
        st.caption("No execution in preview mode. Samples are unrelated to your submission.")
    if submitted:
        st.session_state.pop("result", None)
        if not st.session_state.problem.strip() or not st.session_state.code.strip():
            st.warning("Add both a problem statement and Python code to continue.")
        elif st.session_state.preview:
            st.session_state.result = sample_result()
        else:
            suggestion = suggest_test(st.session_state.problem, st.session_state.code)
            st.session_state.result = find_failing_test(st.session_state.problem, st.session_state.code, suggestion)

with results:
    st.markdown('<div class="panel-label results-label">02 &nbsp; / &nbsp; TEST INSIGHTS</div>', unsafe_allow_html=True)
    render_results(st.session_state.get("result"))
    with st.container(border=True):
        st.markdown("**Look beyond the happy path**")
        st.caption("Good edge cases start at the boundaries of the problem’s valid inputs.")
        st.markdown('<div class="edge-tags"><span>Minimum size</span><span>Repeated values</span><span>Zero & negatives</span><span>Upper limits</span></div>', unsafe_allow_html=True)

st.markdown('''<section id="guide" class="guide"><div class="eyebrow">A LITTLE METHOD. A LOT OF CLARITY.</div><h2>From problem to perspective.</h2><div class="guide-grid">
<article><span>01</span><h3>Set the scene</h3><p>Describe the goal, constraints, and exactly what a correct answer looks like.</p></article>
<article><span>02</span><h3>Bring your logic</h3><p>Paste a complete Python script. Load the example to explore the interface.</p></article>
<article><span>03</span><h3>Read the evidence</h3><p>Preview the sample panel today. Verified failing tests need a connected runner and trusted expected answers.</p></article>
</div></section><footer><div class="brand">⌘ CaseCracker</div><span>Stay curious. Check the boundaries.</span><span>Frontend preview · No code execution</span></footer>''', unsafe_allow_html=True)
