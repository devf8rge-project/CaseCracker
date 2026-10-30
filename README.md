# CaseCracker

A simple Streamlit interface for entering a problem and Python solution, with a
results panel and an optional, clearly labeled temporary sample preview.

**[Open CaseCracker](https://casecracker-itcq4tjahosrmwkimbbxjd.streamlit.app/)**

## Frontend

Midnight black, electric cobalt blue, and acid lime styling with a responsive
workspace, section navigation, and an input guide. Load example fills an
illustrative problem and buggy solution and enables sample mode; Clear resets
the workspace. The Python editor provides syntax highlighting, line numbers,
four-space indentation, and automatic edit syncing. A basic text editor is
available as an alternative. The editor only edits text and does not run code.
Results include test details, an explanation tab, and a JSON download that
preserves the sample and execution status flags.

Editor settings control font size, line numbers, and line wrapping; code can be saved
as `solution.py`. The Compare output tab highlights textual differences between
the displayed outputs. Sample results stay fixed and illustrative, regardless
of the problem or solution entered; they are not generated test results.

Additional workspace tools:

- Editor updates run independently of the surrounding page to avoid full-page
  reruns while typing. Buttons have short hover/press feedback, and Clear offers
  an Undo action. Server actions still depend on network and execution time.
- A brief opening animation shows decorative code over the blurred website,
  then splits outward to reveal the page in about one second. It replays on
  page refresh, but not on ordinary widget updates. Clicking, scrolling, typing,
  or choosing Skip dismisses it immediately; reduced-motion preferences bypass
  it entirely. The overlay does not block interaction with the page.
- Appearance switches between dark and light palettes, including the Python
  editor. The choice is stored in the URL's `theme` parameter so refreshing the
  same page preserves it. A fresh URL without a theme defaults to dark.
- Upload UTF-8 `.py` files up to 200 KB to replace the editor contents.
- Expand workspace uses the full page width and a taller editor; it is not a
  browser fullscreen mode.
- A custom SVG logo and mobile layouts provide larger touch controls and
  stacked panels on narrow screens.

## Run locally

Requires Python 3.10 or newer.

```sh
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

## Deployment

The app is hosted on Streamlit Community Cloud:
[casecracker-itcq4tjahosrmwkimbbxjd.streamlit.app](https://casecracker-itcq4tjahosrmwkimbbxjd.streamlit.app/).

Deployment configuration:

- Repository: `devf8rge-project/CaseCracker`
- Branch: `main`
- Main file: `app.py`
- Dependencies: `requirements.txt`
- Theme: `.streamlit/config.toml` and `assets/style.css`

Updates pushed to `main` are picked up by the connected Streamlit deployment.

## Integration status

- **Secure Execution Runner**: Connected and active (`casecracker/runner.py`). Uses native macOS Seatbelt sandboxing (`sandbox-exec`), network denial, isolated ephemeral filesystem, POSIX CPU/file-size resource limits, AST pre-execution verification, and strict execution timeouts.
- **AI Test Generation**: Boundary stubbed in `casecracker/ai.py` (ready for Gemini/LLM provider integration). The runner automatically extracts examples from problem statements or accepts custom test inputs.

- `app.py`: Streamlit UI, live runner status, workspace, and test execution.
- `casecracker/runner.py`: Secure sandboxed Python execution engine with OS-level isolation.
- `casecracker/execution.py`: Execution boundary coordinating test case matching and output comparison.
- `casecracker/ui.py`: Results panel presentation, comparison diffs, and JSON download.
- `casecracker/models.py`: Shared result types.
- `casecracker/ai.py`: AI test suggestion boundary (ready for AI provider).
- `casecracker/samples.py`: Explicitly synthetic preview data for UI testing.
- `tests/test_runner.py`: Test suite verifying security constraints, timeouts, and execution correctness.
