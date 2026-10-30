"""Explicit draft export/import; no server-side or cross-user storage."""
import json

import streamlit as st


def parse_draft(content: bytes) -> dict:
    if len(content) > 500_000:
        raise ValueError("Choose a draft smaller than 500 KB.")
    data = json.loads(content.decode("utf-8-sig"))
    if not isinstance(data, dict) or data.get("format") != "casecracker-draft-v1":
        raise ValueError("This is not a CaseCracker draft file.")
    if not all(isinstance(data.get(key), str) for key in ("problem", "code")):
        raise ValueError("The draft must contain a problem and code as text.")
    if len(data["code"].encode("utf-8")) > 200_000:
        raise ValueError("Draft code must be smaller than 200 KB.")
    return {"problem": data["problem"], "code": data["code"]}


def restore_draft():
    upload = st.session_state.get("draft_upload")
    if upload is None:
        return
    try:
        data = parse_draft(upload.getvalue())
    except (ValueError, UnicodeDecodeError) as error:
        st.session_state.draft_error = str(error)
        return
    st.session_state.update(data)
    st.session_state.preview = False
    st.session_state.editor_revision = st.session_state.get("editor_revision", 0) + 1
    st.session_state.pop("result", None)
    st.session_state.pop("draft_error", None)


def render_drafts():
    with st.expander("Save or restore a draft"):
        st.caption("Download a draft to keep your problem and code. Upload it here to resume later. Drafts are not saved automatically; refreshing or ending a session may lose unsaved work.")
        st.download_button("Save draft ↓", data=json.dumps({
            "format": "casecracker-draft-v1",
            "problem": st.session_state.get("problem", ""),
            "code": st.session_state.get("code", ""),
        }, indent=2), file_name="casecracker-draft.json", mime="application/json", use_container_width=True)
        st.file_uploader("Restore draft (.json)", type=["json"], key="draft_upload", on_change=restore_draft, help="Restoring replaces the current problem and code. Maximum 500 KB.")
        if st.session_state.get("draft_error"):
            st.error(st.session_state.draft_error)
