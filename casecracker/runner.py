"""Secure Python execution runner with macOS Seatbelt sandbox and resource isolation."""

from __future__ import annotations

import ast
from dataclasses import dataclass
import math
import os
from pathlib import Path
import platform
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
    sandboxed: bool = False


def is_sandbox_available() -> bool:
    """Check if macOS native sandbox-exec is available on this system."""
    return platform.system() == "Darwin" and os.path.isfile("/usr/bin/sandbox-exec") and os.access("/usr/bin/sandbox-exec", os.X_OK)


def execute_code(
    code: str,
    stdin_input: str = "",
    limits: ExecutionLimits = ExecutionLimits(),
) -> ExecutionResult:
    """Execute arbitrary Python code inside an isolated, sandboxed subprocess.

    Security guarantees:
    1. Pre-execution static AST validation (detects syntax errors before spawn).
    2. macOS Seatbelt sandbox:
       - Network access blocked completely (deny network*).
       - Filesystem write blocked everywhere except an ephemeral scratch directory.
    3. POSIX resource limits (CPU limit, max file size limit).
    4. Subprocess wall-clock timeout watchdog.
    5. Isolated Python execution (`python -I -B -u` with sanitized environment).
    6. Truncated output to prevent memory exhaustion bombs.
    """
    # 1. Pre-execution static syntax validation
    try:
        ast.parse(code)
    except SyntaxError as e:
        line_info = f" (line {e.lineno})" if e.lineno else ""
        return ExecutionResult(
            success=False,
            stdout="",
            stderr=f"SyntaxError{line_info}: {e.msg}",
            timed_out=False,
            exit_code=1,
            execution_time_ms=0.0,
            error_message=f"Syntax error{line_info}: {e.msg}",
            sandboxed=False,
        )

    # 2. Ephemeral isolated working directory
    with tempfile.TemporaryDirectory(prefix="casecracker_runner_") as scratch_dir:
        real_scratch = os.path.realpath(scratch_dir)
        script_file = os.path.join(scratch_dir, "solution.py")
        with open(script_file, "w", encoding="utf-8") as f:
            f.write(code)

        sandbox_enabled = is_sandbox_available()

        if sandbox_enabled:
            # Seatbelt profile: allow reading libraries/exec, block network, write only in scratch
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
                "solution.py",
            ]
        else:
            cmd = [
                sys.executable,
                "-I",
                "-B",
                "-u",
                "solution.py",
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
            if not success:
                if "PermissionError" in stderr:
                    error_message = "Security restriction: attempted unauthorized filesystem modification."
                elif "URLError" in stderr or "socket" in stderr.lower():
                    error_message = "Security restriction: network communication is blocked."
                else:
                    error_message = f"Runtime error (exit code {proc.returncode})"

            return ExecutionResult(
                success=success,
                stdout=stdout,
                stderr=stderr,
                timed_out=False,
                exit_code=proc.returncode,
                execution_time_ms=duration_ms,
                error_message=error_message,
                sandboxed=sandbox_enabled,
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
                sandboxed=sandbox_enabled,
            )
        except Exception as exc:
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            return ExecutionResult(
                success=False,
                stdout="",
                stderr=f"Execution failed: {exc}",
                timed_out=False,
                exit_code=1,
                execution_time_ms=duration_ms,
                error_message=f"Execution error: {exc}",
                sandboxed=sandbox_enabled,
            )


def trace_code(code: str, stdin_input: str = "", *, timeout_seconds: float = 1.0) -> dict:
    """Capture at most 100 child-process events; never trace in the app process."""
    import json
    try:
        ast.parse(code)
        template = Path(__file__).with_name('_trace_script.py').read_text()
        script = template.replace('__SOURCE_LITERAL__', repr(code), 1)
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
