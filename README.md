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

- **Execution Runner**: Connected (OS sandbox capability depends on the host) (`casecracker/runner.py`). Uses native macOS Seatbelt sandboxing (`sandbox-exec`), network denial, ephemeral working directory with filesystem write restrictions, POSIX CPU/file-size resource limits, AST syntax validation, and strict execution timeouts.
- **AI Test Generation**: Boundary stubbed in `casecracker/ai.py` (ready for Gemini/LLM provider integration). The runner automatically extracts examples from problem statements or accepts custom test inputs.

- `app.py`: Streamlit UI, live runner status, workspace, and test execution.
- `casecracker/runner.py`: Secure sandboxed Python execution engine with OS-level isolation.
- `casecracker/execution.py`: Execution boundary coordinating test case matching and output comparison.
- `casecracker/ui.py`: Results panel presentation, comparison diffs, and JSON download.
- `casecracker/models.py`: Shared result types.
- `casecracker/ai.py`: AI test suggestion boundary (ready for AI provider).
- `casecracker/samples.py`: Explicitly synthetic preview data for UI testing.
- `tests/test_runner.py`: Test suite verifying security constraints, timeouts, and execution correctness.

## Execution proof demo

1. Open **Execution proof · reference solution & regression tests**.
2. Select **Load execution demo**. This loads a buggy signed-sum solution,
   a trusted reference, a failing input, and three additional regression inputs.
3. Select **Find failing test**. Real runner comparisons populate the reduced
   counterexample and trace tables. Temporary sample mode is disabled for this demo.
4. Optionally request a one-line AI patch or a blind AI prediction in the proof tabs.

`casecracker/checker.py` adds `shrink_failing_input`, `check_suite`, and
`trace_execution_divergence`; the existing runner and execution APIs remain
available. `casecracker/proof_ui.py` presents the evidence.

### Optional AI configuration

Set these in environment variables or `.streamlit/secrets.toml` (never commit keys):

```toml
GEMINI_API_KEY = "your-key"
CASECRACKER_LLM_MODEL = "gemini-2.5-flash"
```

The adapter in `casecracker/ai_helper.py` uses Google's
[generateContent API](https://ai.google.dev/api/generate-content).
`generate_verified_patch(student_code, reference_code, failing_input,
trace_divergence, check_fn)` proposes a one-line change and invokes
`check_fn(patched_code)` before returning verification. The checker callback must
return the `check_suite` report for the failing input and regression suite.
An optional `llm(prompt) -> dict` callable allows another provider or test double.
There are at most three proposals (initial plus two retries). Invalid JSON,
syntax, multi-line edits, timeouts, invalid reference runs, and empty suites
never receive a verified badge. Verification covers the supplied tests only.

The code-only judge request has no access to the reference, problem, traces,
or execution tools. Its prediction is labeled unverified even if it happens to
be right. No AI request occurs without pressing its button. The original
`casecracker/ai.py` automatic edge-case suggestion stub remains unchanged.

### Bounds and interpretation

- Shrinking supports counted arrays (single row or one value per line), single
  integers, and single strings. It preserves counted-array length fields and
  rejects candidates that the reference cannot execute. References must validate
  domain constraints; successful execution alone does not establish valid input.
- Reduction tries at most ten candidates with an approximately three-second
  wall-clock budget. It reports the best reduction found, not global minimality.
  Unsupported formats or execution failures retain the original counterexample.
- Traces record up to 100 events in a child process. Locals are bounded,
  JSON-compatible snapshots taken **before** a line executes. Matching source
  lines are aligned in execution order; different algorithms or variable names
  may not align. The first observed difference is not proof of causality.
  Trace instrumentation is diagnostic, not resistant to tampering by hostile code.
- Runner stdout/stderr are captured to bounded files rather than accumulated in
  memory. Timeouts terminate the process group. POSIX CPU/file limits are used;
  Linux also attempts a 512 MB address-space limit. macOS does **not** enforce
  that address-space limit. The existing Seatbelt profile blocks network and
  restricts writes, but permits host reads; it is not a complete isolation boundary
  for hostile public submissions. Linux/Streamlit Cloud has no Seatbelt sandbox.
  Use a dedicated isolated execution service before accepting untrusted public
  code. The UI distinguishes process-limited checks from OS-sandboxed checks.

Run backend and Streamlit integration tests:

```sh
python -m unittest discover -s tests -v
```

Provider tests use deterministic fake responses; no paid LLM request is required.
