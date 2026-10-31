"""Trusted tracer template executed ONLY inside the existing child runner.

The submitted program is compiled under a distinct filename to exclude tracer
frames. Recorded states are bounded and contain only built-in scalar/containers.
This is an educational trace, not tamper-proof instrumentation of hostile code.
"""
import io
import json
import math
import sys

SOURCE = __SOURCE_LITERAL__
HARNESS = __HARNESS_LITERAL__
steps = []
lines = SOURCE.splitlines()
truncated = False


def safe(value, depth=0):
    kind = type(value)
    if kind in (int, bool):
        return value if kind is bool or value.bit_length() < 256 else '<large integer>'
    if kind is float:
        return value if math.isfinite(value) else str(value)
    if kind is str:
        return value[:160]
    if depth < 2 and kind in (list, tuple):
        return [safe(v, depth + 1) for v in value[:12] if type(v) in (int, bool, float, str, list, tuple, dict)]
    if depth < 2 and kind is dict:
        result = {}
        for index, (key, item) in enumerate(value.items()):
            if index >= 12:
                break
            if type(key) in (str, int) and type(item) in (int, bool, float, str, list, tuple, dict):
                result[str(key)[:80]] = safe(item, depth + 1)
        return result
    return '<omitted>'


def snapshot(frame, event, arg):
    global truncated
    if frame.f_code.co_filename != '<submitted>':
        return snapshot
    if event in ('line', 'return', 'exception'):
        if len(steps) >= 100:
            truncated = True
            sys.settrace(None)
            return None
        variables = {}
        for key, value in frame.f_locals.items():
            if len(variables) >= 20:
                break
            if not key.startswith('__') and type(value) in (int, float, bool, str, list, tuple, dict):
                variables[key] = safe(value)
        steps.append({'line_no': frame.f_lineno, 'code_line': lines[frame.f_lineno-1] if 0 < frame.f_lineno <= len(lines) else '',
                      'event': event, 'locals': variables})
    return snapshot


class BoundedOutput(io.TextIOBase):
    def __init__(self):
        self.parts = []
        self.length = 0
    def write(self, text):
        if self.length < 2048:
            self.parts.append(text[:2048-self.length])
            self.length += len(self.parts[-1])
        return len(text)
    def flush(self):
        pass


output, errors = BoundedOutput(), BoundedOutput()
old_stdout, old_stderr = sys.stdout, sys.stderr
error = None
sys.stdout, sys.stderr = output, errors
try:
    sys.settrace(snapshot)
    namespace = {'__name__': '__main__'}
    exec(compile(SOURCE, '<submitted>', 'exec'), namespace, namespace)
    if HARNESS is not None:
        import types
        target = types.ModuleType('_trace_target')
        target.__dict__.update(namespace)
        sys.modules['_trace_target'] = target
        exec(HARNESS, {'__file__': __file__})
except BaseException as exc:
    if not (isinstance(exc, SystemExit) and exc.code in (None, 0)):
        error = type(exc).__name__
finally:
    sys.settrace(None)
    sys.stdout, sys.stderr = old_stdout, old_stderr
print(json.dumps({'steps': steps, 'truncated': truncated, 'error': error,
                  'stdout': ''.join(output.parts), 'stderr': ''.join(errors.parts)}, allow_nan=False))
