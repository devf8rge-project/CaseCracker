# CaseCracker

A powerful, secure Streamlit testing environment for exploring Python solutions, discovering edge cases, and running test suites with OS-level sandboxing.

**[Open CaseCracker](https://casecracker-itcq4tjahosrmwkimbbxjd.streamlit.app/)**

---

## Testing Engine & Execution Contracts

CaseCracker supports normal Python solutions and runs each test case independently in an isolated, sandboxed subprocess.

### 1. Supported Solution Formats
You can write Python solutions in either of two standard styles:

1. **Standard I/O Mode (`stdin/stdout`)**:
   Read from standard input using `input()` or `sys.stdin.read()` and output answers using `print()`.
   ```python
   n = int(input())
   values = list(map(int, input().split()))
   print(sum(values))
   ```

2. **Function Mode (`def solve`)**:
   Define a top-level `solve(input_data)` function returning the answer. The runner invokes `solve()` with the test case input (or parsed JSON/structure) and captures the return value:
   ```python
   def solve(data):
       values = list(map(int, data.split()))
       return sum(values)
   ```

### 2. Test-Case Format
Each test case consists of:
- **Test Name**: Descriptive label (e.g. `Test 1: Example from problem`, `Edge: Zero value`).
- **Input**: The standard input string passed to `stdin` (or argument to `solve()`).
- **Expected Output**: The expected standard output string to verify against.
- **Explanation (Optional)**: Documentation of what edge case or boundary this test targets.

### 3. Comparison Engine
Outputs are compared robustly using a multi-strategy comparator:
- **Whitespace Normalization**: Automatically normalizes harmless surrounding whitespace, trailing line-end spaces, and newlines.
- **Structured JSON & Literal Equivalence**: Deep equality checking for JSON objects, dictionaries, and lists regardless of key order.
- **Numeric Token Matching with Tolerance**: Floating-point numbers are compared with configurable precision tolerance (`1e-6`).
- **Unified Diff**: If outputs mismatch, a unified diff (`- expected`, `+ actual`) is generated for debugging.

Tests are **never** marked as `PASS` unless the actual output matches according to the verified comparison rule.

### 4. Status Badges & Error Diagnostics
- **`PASS`**: Code executed with exit code 0 and actual output matched expected output.
- **`FAIL`**: Code completed, but output differed from expected output (unified diff displayed).
- **`ERROR`**: Solution raised an unhandled exception (e.g., `ZeroDivisionError`, `IndexError`). Displays readable exception type, offending line number, and clean traceback.
- **`TIMEOUT`**: Execution exceeded the 2.0-second time limit (watchdog terminated the process, preventing infinite loops).
- **`UNVERIFIED`**: Exploratory test run without an expected output; verifies that code executes without crashing or hanging.
- **Pre-execution Syntax Validation**: Checks Python AST before spawning processes, flagging `SyntaxError` with line numbers immediately.

---

## Security & Sandboxing Architecture

Public deployments default to **E2B disposable VMs**, not host subprocesses.
Each code execution gets a fresh VM with outbound internet disabled and a
20-second lifetime. The remote worker clears its environment and uses the
existing execution engine for CPU/file limits, a Linux 512 MB address-space
limit, per-program timeouts, process-group termination, and bounded output.
API keys are not uploaded or forwarded to submitted programs. VM cleanup is
attempted on both success and failure, with VM lifetime as a cleanup backstop.
Missing credentials or provider errors **never fall back to local execution**.

The local runner remains available only through an explicit
`CASECRACKER_RUNNER_BACKEND=local` setting for trusted development code.
Its macOS Seatbelt policy permits host reads and is not suitable for hostile
public code. Do not select the local backend on Streamlit Cloud.

Provider configuration is not evidence of a working service. Use the connection
check and the execution demo after adding credentials; observe actual results.

---

## Frontend & Workspace

- **Compact layout**: Header-level theme controls, a clearly labeled illustrative
  comparison, collapsible test cards, and a primary Find failing test action.
  Repeated edge-case suggestions skip cases already present in the suite.
  Real result summaries include unverified cases alongside passes and failures.
- **Midnight black, electric cobalt, and acid lime styling** with full responsive layout.
- **Code Editor**: Monaco/Ace editor with syntax highlighting, line numbers, automatic edit syncing, and file upload/download (`solution.py`). Basic text editor available as an accessibility toggle.
- **Intro Animation**: Nonblocking split-code opening animation over the blurred workspace.
- **Appearance Switch**: Seamless toggle between Dark and Light mode, preserved in the URL parameter (`?theme=light`).
- **Workspace Actions**: Includes Load example and Clear with an Undo action.
- **Test Management**:
  - Add, edit, and delete multiple custom test cases.
  - **Extract problem cases**: One-click extraction of `Input:` / `Output:` examples from problem statements.
  - **Suggest edge cases**: Generates boundary cases (zeros, negatives, single element, duplicates, empty, upper bounds).
- **Dual Execution Actions**:
  - **▶ Run all tests**: Executes all test cases independently, displaying an aggregated summary matrix (Total, Passed, Failed, Errors, Timed out).
  - **🔎 Find failing test**: Identifies and isolates the first failing or crashing test case.

---

## Connect hosted services

In Streamlit → Manage app → Settings → Secrets, paste the settings below with
real keys. Do not paste keys into chat or commit them to GitHub.

```toml
GEMINI_API_KEY = "your-ai-key"
E2B_API_KEY = "your-sandbox-key"
CASECRACKER_RUNNER_BACKEND = "e2b"
CASECRACKER_LLM_MODEL = "gemini-3.1-flash-lite"
```

Get keys from [Google AI Studio](https://aistudio.google.com/apikey) and the
[E2B dashboard](https://e2b.dev/dashboard). Both services may charge for usage.
The pinned E2B SDK supports
[network-disabled sandbox creation](https://docs.e2b.dev/sdk-reference/python-sdk/v2.5.0/sandbox_sync).
A credential-free template is in `.streamlit/secrets.example.toml`.

After saving secrets and restarting the app:

1. Open the password-protected owner page (`/?view=owner`), sign in, and press
   **Check service connections** under **Service connections & setup**.
2. Confirm both checks pass. No success message is shown before a real check.
3. Load the execution demo and find the failure.
4. Request the AI patch and confirm it passes the displayed regression suite.

No live provider verification is possible until credentials are configured.
Local tests cover adapter behavior with a mocked provider and real worker scripts.

### Owner tools

Setup instructions and connection probes are removed from the public workspace.
To enable the owner page, add `CASECRACKER_OWNER_PASSWORD` in Streamlit Secrets
with a unique random password of at least 16 characters. Open the app with
`?view=owner` and sign in. The URL alone does not grant access. Without that
setting, the page is locked; Streamlit's deployment dashboard is still available
to its authorized owners. Sessions expire after one hour, and changing the
password invalidates existing owner sessions. Sign out when finished.

## Run Locally

Requires Python 3.10 or newer.

```sh
# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# With provider credentials in local secrets.toml:
streamlit run app.py

# OR trusted-code local development only:
CASECRACKER_RUNNER_BACKEND=local streamlit run app.py
```

### Running Unit Tests
The test suite covers passes, assertion failures, runtime crashes, infinite loops/timeouts, syntax preflight, whitespace normalization, numeric tolerance, JSON equality, and sandbox isolation:

```sh
python -m unittest discover -s tests -v
```

---

## Deployment

The app is hosted on Streamlit Community Cloud:
[casecracker-itcq4tjahosrmwkimbbxjd.streamlit.app](https://casecracker-itcq4tjahosrmwkimbbxjd.streamlit.app/).

Deployment configuration:
- Repository: `devf8rge-project/CaseCracker`
- Branch: `main`
- Main file: `app.py`
- Dependencies: `requirements.txt`

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
CASECRACKER_LLM_MODEL = "gemini-3.1-flash-lite"
```

The adapter in `casecracker/ai_helper.py` uses Google's
[Interactions API](https://ai.google.dev/api/interactions-api).
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

### Generate a reference without writing one

In **Execution proof · reference solution & regression tests**, click
**Generate reference from problem** after adding the full problem specification
and at least one example with a known expected output (up to 20). Gemini receives
the specification, not the student's code. The runner checks the generated
candidate against those independent examples before filling the reference field.
Failed candidates are shown but never replace an existing reference. Missing
credentials, malformed output, and runner errors do not produce a passing badge.

Passing examples is not a guarantee of correctness. Execution evidence against
an AI-generated reference is labeled as disagreement with that candidate, rather
than proof of which program is correct on unseen inputs. Changed problems or
examples require regeneration before further reference analysis. These requests
use the configured Gemini and runner services and incur their normal usage.
