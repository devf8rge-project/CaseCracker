"""Server-only settings. Secret values must never appear in the UI or logs."""
import os


def setting(name, default=None):
    value = os.environ.get(name)
    if value is not None:
        return value
    try:
        import streamlit as st
        return st.secrets.get(name, default)
    except (ImportError, FileNotFoundError, RuntimeError):
        return default


def runner_status():
    backend = setting('CASECRACKER_RUNNER_BACKEND', 'e2b')
    return {'backend': backend, 'configured': bool(setting('E2B_API_KEY')) if backend == 'e2b' else backend == 'local',
            'remote': backend == 'e2b', 'ai_configured': bool(setting('GEMINI_API_KEY'))}
