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
Hosting the app does not enable AI generation or code execution; those
integrations remain unconnected.

## Integration status

**No submitted code is executed. No AI provider or execution runner is connected.**
The default button reports this status. Selecting the sample checkbox displays
fixed illustrative data unrelated to the submitted solution, not a real result.

- `app.py`: Streamlit UI and input validation.
- `casecracker/ui.py`: results panel presentation and downloads.
- `casecracker/ai.py`: AI test suggestion boundary (currently a stub).
- `casecracker/execution.py`: execution boundary (currently a stub).
- `casecracker/models.py`: shared result types.
- `casecracker/samples.py`: explicitly synthetic preview data.

To integrate real testing, connect an AI provider and an isolated, resource-limited
runner through these modules. Only report execution after receiving actual runner
results, and only report a failing test after checking output against a trusted
expected answer.
