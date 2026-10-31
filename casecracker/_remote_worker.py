"""Runs inside a disposable E2B VM, never on the website server."""
import importlib.util
import json
import os
import sys
from dataclasses import asdict

# Provider and application keys are never forwarded to this VM.
os.environ.clear()
os.environ['CASECRACKER_ISOLATED_WORKER'] = '1'
spec = importlib.util.spec_from_file_location('cc_engine', '/home/user/cc_engine.py')
engine = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = engine
spec.loader.exec_module(engine)
with open('/home/user/cc_request.json', encoding='utf-8') as source:
    request = json.load(source)
result = engine.execute_code(request['code'], request['input'], engine.ExecutionLimits(**request['limits']))
print(json.dumps(asdict(result)))
