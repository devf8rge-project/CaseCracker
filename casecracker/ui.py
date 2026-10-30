"""Presentation helpers; no execution or AI behavior."""
from __future__ import annotations

import json

import streamlit as st

from casecracker.models import SearchResult


def render_results(result: SearchResult | None) -> None:
    with st.container(border=True):
        if result is None:
            st.markdown('''<div class="empty-result"><div class="orbit"><span>⌕</span></div>
<div class="eyebrow">READY WHEN YOU ARE</div><h3>A small input.<br>A new perspective.</h3>
<p>Your results will live here. Add your problem and solution to get started, or load the example to explore a temporary sample.</p>
<div class="empty-status">No tests executed</div></div>''', unsafe_allow_html=True)
            return
        if result.is_sample:
            st.warning("TEMPORARY SAMPLE — illustrative only; unrelated to your submission. No code was run.")
        elif not result.executed:
            st.info("Not executed — runner integration required.")
        details, explanation = st.tabs(["Test details", "Explanation"])
        with details:
            if result.test_input is None:
                st.write(result.message)
            else:
                st.markdown("**Sample input**" if result.is_sample else "**Test input**")
                st.code(result.test_input, language="text")
                expected, actual = st.columns(2)
                with expected:
                    st.markdown("**Sample expected output**" if result.is_sample else "**Expected output**")
                    st.code(result.expected_output or "", language="text")
                with actual:
                    st.markdown("**Sample hypothetical output**" if result.is_sample else "**Runner output**")
                    st.code(result.actual_output or "", language="text")
        with explanation:
            st.write(result.message)
            st.caption("A verified failure requires actual runner output and a trusted expected answer.")
        st.download_button("Download result ↓", data=json.dumps({
            "is_sample": result.is_sample, "executed": result.executed,
            "message": result.message, "test_input": result.test_input,
            "expected_output": result.expected_output, "actual_output": result.actual_output,
        }, indent=2), file_name="casecracker-sample.json" if result.is_sample else "casecracker-result.json", mime="application/json", use_container_width=True)
    st.caption("Results reflect the last submission. Submit again after editing. Clear resets the workspace.")
