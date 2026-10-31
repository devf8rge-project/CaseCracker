"""Secure Python execution runner with macOS Seatbelt sandbox, resource isolation, and dual execution modes."""

from __future__ import annotations

import ast
from dataclasses import dataclass
import inspect
import math
import os
from pathlib import Path
import platform
import re
import resource
import signal
import subprocess
import sys
import tempfile
import time


@dataclass(frozen=True)
class ExecutionLimits:
    timeout_seconds: float = 2.0
    max_output_bytes: int = 50 * 1024  # 50 KB limit on stdout/stderr
    max_file_size_bytes: int = 1024 * 1024  # 1 MB max file creation limit
    max_memory_bytes: int = 512 * 1024 * 1024


@dataclass(frozen=True)
class ExecutionResult:
    success: bool
    stdout: str
    stderr: str
    timed_out: bool
    exit_code: int | None
    execution_time_ms: float
    error_message: str | None = None
    error_line: int | None = None
    error_traceback: str | None = None
    sandboxed: bool = False
    mode_used: str = "stdin_stdout"  # "solve_function" or "stdin_stdout"


def is_sandbox_available() -> bool:
    """Check if macOS native sandbox-exec is available on this system."""
    return (
        platform.system() == "Darwin"
        and os.path.isfile("/usr/bin/sandbox-exec")
        and os.access("/usr/bin/sandbox-exec", os.X_OK)
    )


def check_syntax(code: str) -> tuple[bool, str | None, int | None]:
    """Validate Python syntax without executing.

    Returns:
        (is_valid, error_message, line_number)
    """
    try:
        ast.parse(code)
        return True, None, None
    except SyntaxError as exc:
        msg = f"SyntaxError on line {exc.lineno}: {exc.msg}"
        return False, msg, exc.lineno


def has_solve_function(code: str) -> bool:
    """Check if user code defines a top-level solve(...) function."""
    try:
        tree = ast.parse(code)
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "solve":
                return True
    except SyntaxError:
        pass
    return False


def _parse_traceback(tb_str: str) -> tuple[int | None, str, str]:
    """Parse stderr traceback to extract the offending user line number, summary, and clean trace."""
    line_match = re.search(r"File \".*solution\.py\", line (\d+)", tb_str)
    line_no = int(line_match.group(1)) if line_match else None

    # Replace temp directory paths with simple filename for clean presentation
    cleaned_tb = re.sub(r"File \".*solution\.py\"", 'File "solution.py"', tb_str.strip())
    # Remove internal harness frames if present
    cleaned_tb = re.sub(r'  File ".*harness\.py", line \d+, in .*\n(    .*\n)*', "", cleaned_tb)

    lines = [l for l in tb_str.strip().splitlines() if l.strip()]
    exc_summary = lines[-1] if lines else "Runtime error"

    return line_no, exc_summary, cleaned_tb


_HARNESS_CODE = """
import sys
import os
import json
import ast
import inspect

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    import solution
except Exception:
    import traceback
    traceback.print_exc()
    sys.exit(1)

if hasattr(solution, "solve") and callable(getattr(solution, "solve")):
    fn = getattr(solution, "solve")
    raw_input = sys.stdin.read()
    cleaned = raw_input.strip()

    parsed_input = None
    if cleaned:
        for parser in (json.loads, ast.literal_eval):
            try:
                parsed_input = parser(cleaned)
                break
            except Exception:
                pass

    try:
        sig = inspect.signature(fn)
        param_count = len(sig.parameters)
    except Exception:
        param_count = 1

    try:
        result = None
        called = False

        # If function expects multiple parameters and parsed_input is a list/tuple of matching length
        if (
            parsed_input is not None
            and isinstance(parsed_input, (list, tuple))
            and param_count == len(parsed_input)
            and param_count > 1
        ):
            try:
                result = fn(*parsed_input)
                called = True
            except TypeError:
                pass

        if not called and parsed_input is not None and param_count == 1:
            try:
                result = fn(parsed_input)
                called = True
            except TypeError:
                pass

        if not called:
            # Fallback to passing raw input string (preserving internal newlines)
            arg = raw_input.rstrip("\\r\\n")
            result = fn(arg)

        if result is not None:
            if isinstance(result, (dict, list)):
                print(json.dumps(result))
            elif isinstance(result, bool):
                print(str(result))
            else:
                print(result)
    except Exception:
        import traceback
        traceback.print_exc()
        sys.exit(1)
else:
    # If solve wasn't callable, exit with notice
    sys.stderr.write("AttributeError: solve function not found or not callable.\\n")
    sys.exit(1)
"""


def execute_code(
    code: str,
    stdin_input: str = "",
    limits: ExecutionLimits = ExecutionLimits(),
) -> ExecutionResult:
    """Execute arbitrary Python code inside an isolated, sandboxed subprocess.

    Security & Reliability Guarantees:
    1. Pre-execution static AST validation (catches syntax errors before spawning).
    2. macOS Seatbelt sandbox:
       - Network access completely denied (deny network*).
       - Filesystem writes blocked everywhere except an ephemeral scratch directory.
    3. POSIX resource limits (CPU time limit, file creation size limit).
    4. Subprocess wall-clock timeout watchdog (kills infinite loops).
    5. Isolated Python execution (`python -I -B -u` with sanitized minimal environment).
    6. Truncated output to prevent memory exhaustion.
    7. Supports both standard `stdin/stdout` scripts and `solve(input_data)` functions.
    """
    # 1. Pre-execution static syntax validation
    valid_syntax, syn_err, syn_line = check_syntax(code)
    if not valid_syntax:
        return ExecutionResult(
            success=False,
            stdout="",
            stderr=syn_err or "SyntaxError",
            timed_out=False,
            exit_code=1,
            execution_time_ms=0.0,
            error_message=syn_err,
            error_line=syn_line,
            error_traceback=syn_err,
            sandboxed=False,
        )

    # Detect execution mode (solve() vs stdin/stdout)
    uses_solve = has_solve_function(code)
    mode_used = "solve_function" if uses_solve else "stdin_stdout"

    # 2. Ephemeral isolated working directory
    with tempfile.TemporaryDirectory(prefix="casecracker_runner_") as scratch_dir:
        real_scratch = os.path.realpath(scratch_dir)
        script_file = os.path.join(scratch_dir, "solution.py")
        with open(script_file, "w", encoding="utf-8") as f:
            f.write(code)

        if uses_solve:
            harness_file = os.path.join(scratch_dir, "harness.py")
            with open(harness_file, "w", encoding="utf-8") as f:
                f.write(_HARNESS_CODE)
            target_script = "harness.py"
        else:
            target_script = "solution.py"

        sandbox_enabled = is_sandbox_available()

        if sandbox_enabled:
            # Seatbelt profile: allow reading standard libraries/exec, block network, write only in scratch
            profile = (
                "(version 1)"
                "(allow default)"
                "(deny network*)"
                "(deny file-write*)"
                f'(allow file-write* (subpath "{scratch_dir}"))'
                f'(allow file-write* (subpath "{real_scratch}"))'
            )
            cmd = [
                "/usr/bin/sandbox-exec",
                "-p",
                profile,
                sys.executable,
                "-I",
                "-B",
                "-u",
                target_script,
            ]
        else:
            cmd = [
                sys.executable,
                "-I",
                "-B",
                "-u",
                target_script,
            ]

        def configure_limits():
            # Enforce CPU limit
            cpu_limit = max(1, math.ceil(limits.timeout_seconds))
            try:
                resource.setrlimit(resource.RLIMIT_CPU, (cpu_limit, cpu_limit + 1))
            except (ValueError, OSError):
                pass

            # RLIMIT_AS is not usable on macOS; report platform limitations in docs.
            if platform.system() != "Darwin" and hasattr(resource, "RLIMIT_AS"):
                try:
                    resource.setrlimit(resource.RLIMIT_AS, (limits.max_memory_bytes, limits.max_memory_bytes))
                except (ValueError, OSError):
                    pass

            # Enforce max file creation size
            try:
                resource.setrlimit(
                    resource.RLIMIT_FSIZE,
                    (limits.max_file_size_bytes, limits.max_file_size_bytes),
                )
            except (ValueError, OSError):
                pass

        # Sanitized minimal environment (prevents leaking host API keys or environment variables)
        sanitized_env = {
            "PATH": "/usr/bin:/bin",
            "PYTHONUNBUFFERED": "1",
            "PYTHONDONTWRITEBYTECODE": "1",
            "LC_ALL": "en_US.UTF-8",
            "LANG": "en_US.UTF-8",
        }

        start_time = time.perf_counter()
        try:
            # Disk-backed streams avoid capture_output accumulating unlimited RAM.
            with tempfile.TemporaryFile() as input_file, tempfile.TemporaryFile() as out_file, tempfile.TemporaryFile() as err_file:
                input_file.write(stdin_input.encode("utf-8"))
                input_file.seek(0)
                proc = subprocess.Popen(
                    cmd, stdin=input_file, stdout=out_file, stderr=err_file,
                    preexec_fn=configure_limits if hasattr(os, "fork") else None,
                    cwd=scratch_dir, env=sanitized_env, start_new_session=True,
                )
                try:
                    proc.wait(timeout=limits.timeout_seconds)
                finally:
                    try:
                        os.killpg(proc.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                    proc.wait()
                out_file.seek(0)
                err_file.seek(0)
                stdout_bytes = out_file.read(limits.max_output_bytes + 1)
                stderr_bytes = err_file.read(limits.max_output_bytes + 1)
                proc.stdout = stdout_bytes.decode("utf-8", errors="replace")
                proc.stderr = stderr_bytes.decode("utf-8", errors="replace")
            duration_ms = (time.perf_counter() - start_time) * 1000.0

            # Output stream bounding
            stdout = proc.stdout
            if len(stdout.encode("utf-8")) > limits.max_output_bytes:
                stdout = stdout[: limits.max_output_bytes] + "\n... [Output truncated: size limit exceeded]"

            stderr = proc.stderr
            if len(stderr.encode("utf-8")) > limits.max_output_bytes:
                stderr = stderr[: limits.max_output_bytes] + "\n... [Error truncated: size limit exceeded]"

            success = proc.returncode == 0
            error_message = None
            error_line = None
            error_traceback = None

            if not success:
                if "PermissionError" in stderr:
                    error_message = "Security restriction: attempted unauthorized filesystem modification."
                elif "URLError" in stderr or "socket" in stderr.lower():
                    error_message = "Security restriction: network communication is blocked."
                else:
                    line_no, exc_summary, cleaned_tb = _parse_traceback(stderr)
                    error_message = exc_summary
                    error_line = line_no
                    error_traceback = cleaned_tb

            return ExecutionResult(
                success=success,
                stdout=stdout,
                stderr=stderr,
                timed_out=False,
                exit_code=proc.returncode,
                execution_time_ms=duration_ms,
                error_message=error_message,
                error_line=error_line,
                error_traceback=error_traceback or (stderr if not success else None),
                sandboxed=sandbox_enabled,
                mode_used=mode_used,
            )

        except subprocess.TimeoutExpired:
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            return ExecutionResult(
                success=False,
                stdout="",
                stderr=f"TimeoutExpired: Execution exceeded limit of {limits.timeout_seconds:.1f}s",
                timed_out=True,
                exit_code=None,
                execution_time_ms=duration_ms,
                error_message=f"Time Limit Exceeded (> {limits.timeout_seconds:.1f}s)",
                error_line=None,
                error_traceback="Process was terminated because it exceeded the per-test execution timeout.",
                sandboxed=sandbox_enabled,
                mode_used=mode_used,
            )
        except Exception as exc:
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            return ExecutionResult(
                success=False,
                stdout="",
                stderr=f"Execution error: {exc}",
                timed_out=False,
                exit_code=1,
                execution_time_ms=duration_ms,
                error_message=f"Execution error: {exc}",
                error_line=None,
                error_traceback=str(exc),
                sandboxed=sandbox_enabled,
                mode_used=mode_used,
            )


def trace_code(code: str, stdin_input: str = "", *, timeout_seconds: float = 1.0) -> dict:
    """Capture at most 100 child-process events; never trace in the app process."""
    import json
    try:
        ast.parse(code)
        template = Path(__file__).with_name('_trace_script.py').read_text()
        script = template.replace('__SOURCE_LITERAL__', repr(code), 1)
        harness = _HARNESS_CODE.replace('    import solution', "    solution = sys.modules['_trace_target']") if has_solve_function(code) else None
        script = script.replace('__HARNESS_LITERAL__', repr(harness), 1)
        result = execute_code(script, stdin_input, ExecutionLimits(
            timeout_seconds=timeout_seconds, max_output_bytes=512 * 1024,
        ))
        if not result.success:
            return {"steps": [], "error": result.error_message or result.stderr,
                    "timed_out": result.timed_out, "sandboxed": result.sandboxed}
        payload = json.loads(result.stdout)
        if not isinstance(payload, dict) or not isinstance(payload.get('steps'), list):
            raise ValueError('Invalid trace')
        payload['steps'] = payload['steps'][:100]
        payload['sandboxed'] = result.sandboxed
        return payload
    except Exception:
        return {"steps": [], "error": "Trace unavailable or invalid; use the normal execution result."}
