"""Streamlit presentation layer for CaseCracker."""

from pathlib import Path

import streamlit as st

from casecracker.ai import suggest_test
from casecracker.execution import find_failing_test
from casecracker.samples import sample_result


st.set_page_config(page_title="CaseCracker · Find your edge case", page_icon="🔎", layout="wide")
stylesheet = Path(__file__).parent / "assets" / "style.css"
st.markdown(f"<style>{stylesheet.read_text()}</style>", unsafe_allow_html=True)
brand, status = st.columns([3, 1])
with brand:
    st.markdown('<div class="brand"><span>⌘</span> CaseCracker</div>', unsafe_allow_html=True)
with status:
    st.caption("● Preview · Python")
st.markdown(
    '<div class="eyebrow">SMALL INPUTS. BIG REVELATIONS.</div>'
    '<h1 class="hero-title">Good solution.<br>What about the <span>edge cases?</span></h1>'
    '<p class="hero-description">Give your solution a second look. Add the problem, '
    'paste your Python code, and explore what a failing test could look like.</p>',
    unsafe_allow_html=True,
)
st.info("Preview mode: AI and runner are not connected. Your code will not be executed.")
workspace, results = st.columns([1.35, 1], gap="large")

with workspace, st.form("casecracker"):
    st.subheader("01 / Your workspace")
    st.markdown('<p class="section-note">Start with the problem. Then add your solution.</p>', unsafe_allow_html=True)
    problem = st.text_area(
        "Problem statement",
        height=180,
        placeholder="Describe the task, input/output format, and constraints…",
    )
    code = st.text_area(
        "Python code",
        height=300,
        placeholder="Paste your Python solution here…",
    )
    preview = st.checkbox("Show temporary sample results (illustration only)")
    submitted = st.form_submit_button("Find failing test →", type="primary", use_container_width=True)
    st.caption("Python only · Include the input/output format and constraints for context.")

if submitted:
    # Clear earlier output so invalid submissions cannot display stale results.
    st.session_state.pop("result", None)
    if not problem.strip() or not code.strip():
        st.warning("Enter both a problem statement and Python code.")
    elif preview:
        st.session_state.result = sample_result()
    else:
        suggestion = suggest_test(problem, code)
        st.session_state.result = find_failing_test(problem, code, suggestion)

with results:
    st.subheader("02 / Results")
    st.markdown('<p class="section-note">A closer look at the case that matters.</p>', unsafe_allow_html=True)
    result = st.session_state.get("result")
    if result is None:
        st.markdown(
            '<div class="empty-result"><div class="symbol">⌕</div>'
            '<h3>Your next discovery starts here</h3>'
            '<p>Add a problem and your code, then select<br>Find failing test to continue.</p>'
            '<p>Want to explore the layout?<br>Enable the temporary sample results option.</p></div>',
            unsafe_allow_html=True,
        )
    if result is not None:
        with st.container(border=True):
            if result.is_sample:
                st.warning("TEMPORARY SAMPLE — illustrative only; unrelated to your submission. No code was run.")
            elif not result.executed:
                st.info("Not executed — runner integration required.")
            st.write(result.message)
            if result.test_input is not None:
                st.markdown("**Sample input**" if result.is_sample else "**Test input**")
                st.code(result.test_input, language="text")
            expected, actual = st.columns(2)
            if result.expected_output is not None:
                with expected:
                    st.markdown("**Sample expected output**" if result.is_sample else "**Expected output**")
                    st.code(result.expected_output, language="text")
            if result.actual_output is not None:
                with actual:
                    st.markdown("**Sample hypothetical output**" if result.is_sample else "**Runner output**")
                    st.code(result.actual_output, language="text")
        st.caption("Results reflect the last submitted form values.")

    with st.container(border=True):
        st.markdown("**A useful problem statement includes**")
        st.write("The goal, valid input ranges, expected output, and at least one example.")
        st.caption("Edge cases often live at the boundaries: empty inputs, duplicates, zeros, and large values.")

st.markdown('<div class="footer">CaseCracker · A little curiosity for every solution.</div>', unsafe_allow_html=True)
