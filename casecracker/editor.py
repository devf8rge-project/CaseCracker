"""Python editor presentation; never executes user input."""
import streamlit as st
from streamlit_ace import st_ace


def reset_editor_instance():
    st.session_state.editor_revision = st.session_state.get("editor_revision", 0) + 1


def import_python():
    uploaded = st.session_state.get("python_upload")
    if uploaded is None:
        return
    try:
        if uploaded.size > 200_000:
            raise ValueError("Choose a Python file smaller than 200 KB.")
        code = uploaded.getvalue().decode("utf-8-sig")
    except (UnicodeDecodeError, ValueError) as error:
        st.session_state.upload_error = str(error)
        return
    st.session_state.code = code
    st.session_state.pop("upload_error", None)
    st.session_state.pop("result", None)
    reset_editor_instance()


@st.fragment
def render_editor() -> None:
    st.markdown("**Python code**")
    with st.expander("Upload a Python file"):
        st.file_uploader("Choose a .py file", type=["py"], key="python_upload", on_change=import_python, help="UTF-8, up to 200 KB. Selecting a file replaces the editor contents; it does not run the file.")
        if st.session_state.get("upload_error"):
            st.error(st.session_state.upload_error)
    with st.expander("Editor settings"):
        font_size = st.select_slider("Font size", options=[12, 14, 16, 18, 20], value=14)
        wrap = st.checkbox("Wrap long lines", value=True)
        show_gutter = st.checkbox("Show line numbers", value=True)
        plain = st.checkbox("Use basic text editor", key="basic_editor", on_change=reset_editor_instance, help="A standard text box for screen readers or devices where the code editor is inconvenient.")
    height = 620 if st.session_state.get("expanded_workspace") else 340
    revision = st.session_state.get("editor_revision", 0)
    if plain:
        value = st.text_area("Python code", value=st.session_state.get("code", ""), height=height, key=f"plain_code_{revision}", label_visibility="collapsed", placeholder="# Paste your complete Python solution here…")
    else:
        theme = "chrome" if st.session_state.get("color_mode") == "Light" else "tomorrow_night"
        value = st_ace(value=st.session_state.get("code", ""), language="python", theme=theme, key=f"python_editor_{revision}", font_size=font_size, tab_size=4, show_gutter=show_gutter, show_print_margin=False, wrap=wrap, auto_update=True, min_lines=16, height=height)
    if value is not None:
        st.session_state.code = value
    code = st.session_state.get("code", "")
    st.caption(f"Python · {len(code.splitlines())} lines · {len(code)} characters · Tab: 4 spaces")
    if not plain:
        st.caption("Tab to indent · Esc then Tab to leave the editor")
    st.download_button("Download Python file ↓", data=code, file_name="solution.py", mime="text/x-python", disabled=not code.strip(), use_container_width=True)
