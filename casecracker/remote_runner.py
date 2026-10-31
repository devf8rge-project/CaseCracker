"""Disposable, network-disabled E2B runner. Never falls back to host execution."""
from dataclasses import asdict
import json
import math
import re
from pathlib import Path
import time

from casecracker.settings import setting


def execute_remote(code, stdin_input, limits):
    from casecracker.runner import ExecutionResult, has_solve_function
    start = time.monotonic()
    deadline = start + limits.total_budget_seconds if limits.total_budget_seconds is not None else None
    sandbox = None
    def request_budget():
        remaining = deadline - time.monotonic() if deadline is not None else 8
        if remaining <= .01:
            raise TimeoutError('Execution budget exhausted')
        return min(8, remaining)
    def unavailable(message):
        return ExecutionResult(success=False, stdout='', stderr=message, timed_out=False,
                               exit_code=None, execution_time_ms=(time.monotonic()-start)*1000,
                               error_message=message, sandboxed=False)
    api_key = setting('E2B_API_KEY')
    if not api_key:
        return unavailable('Hosted runner not configured. Add E2B_API_KEY to server secrets. No submitted code was executed.')
    if len(code.encode('utf-8')) > 200_000 or len(stdin_input.encode('utf-8')) > 200_000:
        return unavailable('Code and input must each be at most 200 KB. No submitted code was executed.')
    phase = 'loading SDK'
    try:
        from e2b import Sandbox
        # Each execution gets a fresh VM: no cross-user or cross-test reuse.
        phase = 'creating sandbox'
        sandbox = Sandbox.create(api_key=api_key, secure=True, allow_internet_access=False,
                                 timeout=20, request_timeout=request_budget())
        root = Path(__file__).parent
        phase = 'uploading worker'
        for destination, content in [
            ('cc_engine.py', (root / 'runner.py').read_text()),
            ('cc_worker.py', (root / '_remote_worker.py').read_text()),
            ('cc_request.json', json.dumps({'code': code, 'input': stdin_input, 'limits': asdict(limits)})),
        ]:
            sandbox.files.write('/home/user/' + destination, content, request_timeout=request_budget())
        phase = 'executing worker'
        # e2b-connect 2.5 serializes seconds as str(timeout * 1000).
        # Floats produce an invalid Connect-Timeout-Ms value such as 7000.0.
        command_timeout = max(1, math.ceil(min(limits.timeout_seconds + 5, request_budget())))
        command = sandbox.commands.run('python3 -I -B /home/user/cc_worker.py',
                                       timeout=command_timeout, request_timeout=request_budget())
        phase = 'reading worker result'
        data = json.loads(command.stdout)
        # Only the existing bounded runner result schema is accepted.
        if not isinstance(data, dict) or type(data.get('success')) is not bool or not isinstance(data.get('stdout'), str):
            raise ValueError('Invalid worker response')
        fields = ExecutionResult.__dataclass_fields__
        result = {key: value for key, value in data.items() if key in fields}
        result['sandboxed'] = True
        result['mode_used'] = 'solve_function' if has_solve_function(code) else 'stdin_stdout'
        return ExecutionResult(**result)
    except Exception as exc:
        # SDK exceptions can include credential-bearing URLs: never display them.
        status = getattr(exc, 'status_code', None)
        code = f' HTTP {status}' if type(status) is int else ''
        kind = type(exc).__name__[:60]
        detail = str(exc).replace(api_key, '[redacted]')
        detail = re.sub(r'https?://\S+', '[endpoint]', detail)
        detail = re.sub(r'[A-Za-z0-9_.=\-]{24,}', '[redacted]', detail)
        detail = ' '.join(detail.split())[:240]
        return unavailable(f'Hosted runner failed while {phase} ({kind}{code}): {detail}. No local fallback was used.')
    finally:
        if sandbox is not None:
            try:
                sandbox.kill(request_timeout=min(1, max(.05, deadline - time.monotonic())) if deadline is not None else 5)
            except Exception:
                pass  # The 20-second VM lifetime remains a cleanup backstop.
