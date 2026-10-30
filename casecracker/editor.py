"""Python editor presentation; never executes user input."""
import streamlit as st
from streamlit_ace import st_ace


def reset_editor_instance():
    st.session_state.editor_revision = st.session_state.get("editor_revision", 0) + 1


def render_editor() -> None:
    st.markdown("**Python code**")
    with st.expander("Editor settings"):
        font_size = st.select_slider("Font size", options=[12, 14, 16, 18, 20], value=14)
        wrap = st.checkbox("Wrap long lines", value=True)
        show_gutter = st.checkbox("Show line numbers", value=True)
    plain = st.checkbox("Use basic text editor", key="basic_editor", on_change=reset_editor_instance, help="A standard text box for screen readers or devices where the code editor is inconvenient.")
    revision = st.session_state.get("editor_revision", 0)
    if plain:
        value = st.text_area("Python code", value=st.session_state.get("code", ""), height=340, key=f"plain_code_{revision}", label_visibility="collapsed", placeholder="# Paste your complete Python solution here…")
    else:
        value = st_ace(value=st.session_state.get("code", ""), language="python", theme="tomorrow_night", key=f"python_editor_{revision}", font_size=font_size, tab_size=4, show_gutter=show_gutter, show_print_margin=False, wrap=wrap, auto_update=True, min_lines=16, height=340)
    if value is not None:
        st.session_state.code = value
    code = st.session_state.get("code", "")
    st.caption(f"Python · {len(code.splitlines())} lines · {len(code)} characters · Tab: 4 spaces")
    if not plain:
        st.caption("Edits sync automatically after typing. Use Tab to indent; Esc, then Tab to move focus out of the editor.")
    st.download_button("Download Python file ↓", data=code, file_name="solution.py", mime="text/x-python", disabled=not code.strip(), use_container_width=True)
