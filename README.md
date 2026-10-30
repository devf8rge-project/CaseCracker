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

User code is **never** executed inside the Streamlit host process. Every test runs in a dedicated ephemeral subprocess with multi-layer boundaries:

- **macOS Seatbelt Sandbox (`/usr/bin/sandbox-exec`)**:
  - `(deny network*)`: All incoming and outgoing network sockets are blocked.
  - `(deny file-write*)`: Filesystem write access is denied everywhere on the machine except inside a temporary scratch directory created for that specific test run.
- **POSIX Resource Limits (`resource.setrlimit`)**:
  - CPU time limit (`RLIMIT_CPU`)
  - File size limit (`RLIMIT_FSIZE`, max 1 MB)
- **Watchdog Timeout**: Subprocess terminated after 2.0s wall clock.
- **Output Truncation**: stdout and stderr capped at 50 KB to prevent memory exhaustion attacks.
- **Process Sanitization**: Executes under `python -I -B -u` with stripped environment variables (`PATH=/usr/bin:/bin`).
- **Guaranteed Cleanup**: Temporary directories and process handles are always reclaimed in `try...finally` blocks.

---

## Frontend & Workspace

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

## Run Locally

Requires Python 3.10 or newer.

```sh
# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run Streamlit application
streamlit run app.py
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
