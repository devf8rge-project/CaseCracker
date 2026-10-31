"""Server-only settings. Secret values must never appear in the UI or logs."""
import os


def setting(name, default=None):
    value = os.environ.get(name)
    if value is not None:
        return value
    # Loading st.secrets exports top-level values to os.environ. Preserve an
    # explicit backend override (e.g. trusted local tests) while reading a key.
    explicit_backend = os.environ.get('CASECRACKER_RUNNER_BACKEND')
    try:
        import streamlit as st
        return st.secrets.get(name, default)
    except (ImportError, FileNotFoundError, RuntimeError):
        return default
    finally:
        if explicit_backend is not None:
            os.environ['CASECRACKER_RUNNER_BACKEND'] = explicit_backend


def runner_status():
    backend = setting('CASECRACKER_RUNNER_BACKEND', 'e2b')
    return {'backend': backend, 'configured': bool(setting('E2B_API_KEY')) if backend == 'e2b' else backend == 'local',
            'remote': backend == 'e2b', 'ai_configured': bool(setting('GEMINI_API_KEY'))}
