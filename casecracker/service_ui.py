"""Credential-free service status and explicit connection checks."""
import streamlit as st
from casecracker.settings import runner_status, setting


def render_service_status():
    status = runner_status()
    with st.expander('Service connections & setup'):
        st.write('Runner: ' + ('configured (not yet checked)' if status['configured'] else 'not configured'))
        st.write('AI: ' + ('key configured (not yet checked)' if status['ai_configured'] else 'not configured'))
        st.caption('Keys stay in server secrets. Configuration alone does not confirm a working connection.')
        st.caption('Selected AI model: ' + str(setting('CASECRACKER_LLM_MODEL', 'gemini-flash-latest')))
        if not status['configured'] or not status['ai_configured']:
            st.markdown('In Streamlit → Manage app → Settings → Secrets, add:')
            st.code('GEMINI_API_KEY = "your-ai-key"\nE2B_API_KEY = "your-sandbox-key"\nCASECRACKER_RUNNER_BACKEND = "e2b"\nCASECRACKER_LLM_MODEL = "gemini-flash-latest"', language='toml')
            st.markdown('[Get an AI key](https://aistudio.google.com/apikey) · [Get a sandbox key](https://e2b.dev/dashboard)')
        st.caption('Check connections sends a small AI request and starts one short-lived sandbox; provider usage may be charged.')
        if st.button('Check service connections'):
            checks = {}
            details = {}
            if status['configured']:
                from casecracker.runner import execute_code
                with st.spinner('Checking the execution connection…'):
                    result = execute_code('print("casecracker-ready")')
                checks['runner'] = result.success and result.stdout.strip() == 'casecracker-ready'
                if not checks['runner']:
                    details['runner'] = result.error_message or 'Worker response did not match the connection probe.'
            else:
                checks['runner'] = False
            if status['ai_configured']:
                from casecracker.ai_helper import make_llm
                try:
                    with st.spinner('Checking the AI connection…'):
                        reply = make_llm(setting('GEMINI_API_KEY'), setting('CASECRACKER_LLM_MODEL'))('Return exactly this JSON object: {"ready": true}')
                    checks['ai'] = reply.get('ready') is True
                except ValueError as error:
                    checks['ai'] = False
                    details['ai'] = str(error)
                except Exception:
                    checks['ai'] = False
                    details['ai'] = 'AI connection unavailable.'
            else:
                checks['ai'] = False
            st.session_state.service_checks = checks
            st.session_state.service_check_details = details
        for name, passed in st.session_state.get('service_checks', {}).items():
            if passed:
                st.success(f'{name.title()}: connection check passed.')
            else:
                st.warning(f'{name.title()}: not connected. Check server credentials, quota, and network access.')
                detail = st.session_state.get('service_check_details', {}).get(name)
                if detail:
                    st.caption(detail)
