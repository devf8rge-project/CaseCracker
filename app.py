"""Streamlit presentation layer for CaseCracker."""

import streamlit as st

from casecracker.ai import suggest_test
from casecracker.execution import find_failing_test
from casecracker.samples import sample_result


st.set_page_config(page_title="CaseCracker", page_icon="🔎", layout="centered")
st.title("CaseCracker")
st.write("Find the edge case your solution missed.")
st.info("Runner and AI are not connected. Submitted code will not be executed.")

with st.form("casecracker"):
    problem = st.text_area(
        "Problem statement",
        height=160,
        placeholder="Describe the task, input/output format, and constraints…",
    )
    code = st.text_area(
        "Python code",
        height=260,
        placeholder="Paste your Python solution here…",
    )
    preview = st.checkbox("Show temporary sample results (illustration only)")
    submitted = st.form_submit_button("Find failing test", type="primary")

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

st.subheader("Results")
result = st.session_state.get("result")
if result is None:
    st.caption("Submit a problem and solution to see the connection status or a sample preview.")
else:
    with st.container(border=True):
        if result.is_sample:
            st.warning("TEMPORARY SAMPLE — illustrative only; unrelated to your submission. No code was run.")
        elif not result.executed:
            st.info("Not executed — runner integration required.")
        st.write(result.message)
        if result.test_input is not None:
            st.markdown("**Sample input**" if result.is_sample else "**Test input**")
            st.code(result.test_input, language="text")
        if result.expected_output is not None:
            st.markdown("**Sample expected output**" if result.is_sample else "**Expected output**")
            st.code(result.expected_output, language="text")
        if result.actual_output is not None:
            st.markdown("**Sample hypothetical output**" if result.is_sample else "**Runner output**")
            st.code(result.actual_output, language="text")
    st.caption("Results reflect the last submitted form values.")
