"""Owner tools guarded by a server-side password; closed when unconfigured."""
import hashlib
import hmac
import time

import streamlit as st

from casecracker.service_ui import render_service_status
from casecracker.settings import setting


def _fingerprint(password):
    return hashlib.sha256(password.encode('utf-8')).hexdigest()


def _login():
    supplied = st.session_state.pop('owner_password_input', '')
    configured = setting('CASECRACKER_OWNER_PASSWORD', '')
    now = time.time()
    if now < st.session_state.get('owner_retry_after', 0):
        return
    if isinstance(configured, str) and len(configured) >= 16 and hmac.compare_digest(supplied.encode('utf-8'), configured.encode('utf-8')):
        st.session_state.owner_auth = (_fingerprint(configured), now)
        st.session_state.pop('owner_login_error', None)
        st.session_state.owner_attempts = 0
    else:
        attempts = st.session_state.get('owner_attempts', 0) + 1
        st.session_state.owner_attempts = attempts
        st.session_state.owner_login_error = 'Password not accepted.'
        if attempts % 5 == 0:
            st.session_state.owner_retry_after = now + 30


def _logout():
    for key in ('owner_auth', 'service_checks', 'service_check_details', 'owner_password_input'):
        st.session_state.pop(key, None)


def render_owner_page():
    st.title('Owner settings')
    st.markdown('[← Back to CaseCracker](?theme=dark)')
    configured = setting('CASECRACKER_OWNER_PASSWORD', '')
    if not isinstance(configured, str) or len(configured) < 16:
        st.info('Owner tools are unavailable. Use your deployment dashboard to manage the app.')
        return
    auth = st.session_state.get('owner_auth')
    allowed = (auth and hmac.compare_digest(auth[0], _fingerprint(configured))
               and 0 <= time.time() - auth[1] < 3600)
    if not allowed:
        if time.time() < st.session_state.get('owner_retry_after', 0):
            st.warning('Too many attempts. Wait 30 seconds before trying again.')
        with st.form('owner_sign_in'):
            st.text_input('Owner password', type='password', key='owner_password_input')
            st.form_submit_button('Sign in', on_click=_login)
        if st.session_state.get('owner_login_error'):
            st.error(st.session_state.owner_login_error)
        return
    st.button('Sign out', on_click=_logout)
    render_service_status()
