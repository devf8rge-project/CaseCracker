"""Decorative page entrance, independent of code execution."""
from pathlib import Path

import streamlit.components.v1 as components


def render_intro():
    source = Path(__file__).resolve().parent.parent / 'assets' / 'intro.html'
    components.html(source.read_text(), height=0, scrolling=False)
