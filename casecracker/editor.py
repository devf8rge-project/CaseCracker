"""Python editor presentation; never executes user input."""
import streamlit as st
from streamlit_ace import st_ace


def reset_editor_instance():
    st.session_state.editor_revision = st.session_state.get("editor_revision", 0) + 1


def render_editor() -> None:
    st.markdown("**Python code**")
    plain = st.checkbox("Use basic text editor", key="basic_editor", on_change=reset_editor_instance, help="A standard text box for screen readers or devices where the code editor is inconvenient.")
    revision = st.session_state.get("editor_revision", 0)
    if plain:
        value = st.text_area("Python code", value=st.session_state.get("code", ""), height=340, key=f"plain_code_{revision}", label_visibility="collapsed", placeholder="# Paste your complete Python solution here…")
    else:
        value = st_ace(value=st.session_state.get("code", ""), language="python", theme="tomorrow_night", key=f"python_editor_{revision}", font_size=14, tab_size=4, show_gutter=True, show_print_margin=False, wrap=True, auto_update=True, min_lines=16, height=340)
    if value is not None:
        st.session_state.code = value
    code = st.session_state.get("code", "")
    st.caption(f"Python · {len(code.splitlines())} lines · {len(code)} characters · Tab: 4 spaces")
    if not plain:
        st.caption("Edits sync automatically after typing. Use Tab to indent; Esc, then Tab to move focus out of the editor.")
