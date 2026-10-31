"""UI for bounded, execution-grounded evidence and optional AI proposals."""
from __future__ import annotations
import json

import pandas as pd
import streamlit as st

from casecracker.ai_helper import generate_verified_patch, guess_failing_case, make_llm
from casecracker.checker import check_suite, shrink_failing_input, trace_execution_divergence
from casecracker.execution import extract_test_cases_from_problem
from casecracker.models import SearchResult


def parse_suite(raw):
    values = json.loads(raw or '[]')
    if not isinstance(values, list) or len(values) > 20 or not all(isinstance(x, str) and len(x) <= 10000 for x in values):
        raise ValueError('Provide a JSON array of at most 20 stdin strings, each up to 10,000 characters.')
    return values


def analyze_reference(problem, student, reference, custom_input, extra_tests):
    inputs = parse_suite(extra_tests)
    if custom_input:
        inputs.insert(0, custom_input)
    inputs.extend(inp for inp, _ in extract_test_cases_from_problem(problem))
    inputs = list(dict.fromkeys(inputs))
    if not inputs or len(inputs) > 20:
        raise ValueError('Provide 1–20 total distinct test inputs through custom input, problem samples, or regression tests.')
    report = check_suite(student, reference, inputs)
    bundle = {'student': student, 'reference': reference, 'inputs': inputs, 'report': report,
              'problem': problem, 'custom_input': custom_input, 'extra_tests': extra_tests}
    failure = next((c for c in report['cases'] if c['valid'] and c['failed']), None)
    if failure:
        reduced = shrink_failing_input(student, reference, failure['input'])
        # Always retain the original, already-confirmed result if reduction fails.
        text = reduced['shrunk_failing_input'] if reduced['is_failure'] else failure['input']
        bundle.update(shrink=reduced, failure=failure,
                      trace=trace_execution_divergence(student, reference, text), failing_input=text)
        return SearchResult(executed=True, passed=False, message='Failure reproduced against the supplied reference.',
                            test_input=text, expected_output=reduced['expected'] if reduced['is_failure'] else failure['expected'],
                            actual_output=reduced['actual'] if reduced['is_failure'] else failure['actual'],
                            error=reduced['error'] or failure.get('error'), sandboxed=failure['sandboxed']), bundle
    if not report['is_verified']:
        return SearchResult(executed=False, message='Reference execution was invalid or unavailable for one or more tests. No correctness claim made.'), bundle
    return SearchResult(executed=True, passed=True, message=f"Passed all {report['total_count']} supplied reference tests.",
                        sandboxed=report['sandboxed']), bundle


def _provider():
    try:
        key = st.secrets.get('GEMINI_API_KEY')
        model = st.secrets.get('CASECRACKER_LLM_MODEL')
    except (FileNotFoundError, st.errors.StreamlitSecretNotFoundError):
        key = model = None
    return make_llm(key, model)


def _trace_table(records):
    if not records:
        st.caption('No trace records available.')
        return
    frame = pd.DataFrame([{
        'Step': i + 1, 'Line': r['line_no'], 'Event': r['event'],
        'Source (before execution)': r['code_line'], 'Variables': json.dumps(r['locals'], ensure_ascii=False),
    } for i, r in enumerate(records)])
    if st.session_state.get('color_mode') == 'Light':
        frame = frame.style.set_properties(**{'background-color': '#ffffff', 'color': '#162039'})
    st.dataframe(frame, hide_index=True, use_container_width=True)


def render_proof_tools():
    bundle = st.session_state.get('proof_bundle')
    if not bundle:
        return
    st.divider()
    st.subheader('Execution evidence')
    st.caption('Evidence is relative to your supplied reference and tests, not a proof for every possible input. The reference must enforce valid input constraints.')
    report = bundle['report']
    st.write(f"Original suite: {report['passed_count']} / {report['total_count']} matched the reference.")
    if 'failure' not in bundle:
        return
    stale = (bundle['student'] != st.session_state.get('code', '').strip() or
             bundle['reference'] != st.session_state.get('reference_code', '').strip() or
             bundle['problem'] != st.session_state.get('problem', '').strip() or
             bundle['custom_input'] != st.session_state.get('custom_input', '') or
             bundle['extra_tests'] != st.session_state.get('regression_inputs', ''))
    if stale:
        st.warning('Code or tests have changed. This evidence belongs to the last submission. Submit again before requesting AI analysis.')
    shrink = bundle['shrink']
    st.markdown('#### Minimal counterexample · best found within budget')
    original, reduced = st.columns(2)
    with original:
        st.markdown('**Raw failing input**')
        st.code(bundle['failure']['input'], language='text')
    with reduced:
        st.markdown('**→ Auto-shrunk input**')
        st.code(bundle['failing_input'], language='text')
    before, after = len(bundle['failure']['input']), len(bundle['failing_input'])
    st.caption(f"{before} → {after} characters · {shrink['iterations']} reduction trials · {shrink['status']}. {shrink['minimality']}")
    trace = bundle['trace']
    st.markdown('#### Variable divergence explorer')
    st.write(trace['summary'])
    st.caption(trace['alignment'])
    aligned, left_trace, right_trace = st.tabs(['Aligned states', 'Student trace', 'Reference trace'])
    with aligned:
        records = trace['aligned_steps']
        if records:
            frame = pd.DataFrame([{
                'Student step': r['student_step'], 'Reference step': r['reference_step'],
                'Source': r['code_line'], 'Student variables': json.dumps(r['student_locals']),
                'Reference variables': json.dumps(r['reference_locals']),
                'Different variables': ', '.join(r['differences']),
            } for r in records])
            first = next((i for i, r in enumerate(records) if r['differences']), None)
            styled = frame.style
            if st.session_state.get('color_mode') == 'Light':
                styled = styled.set_properties(**{'background-color': '#ffffff', 'color': '#162039'})
            styled = styled.apply(lambda row: ['background-color: #684b12; color: #ffffff' if row.name == first else '' for _ in row], axis=1)
            st.dataframe(styled, hide_index=True, use_container_width=True)
        else:
            st.info('These traces could not be aligned reliably. Use the separate trace tabs.')
    for panel, key, status_key in [(left_trace, 'student_steps', 'student_status'), (right_trace, 'reference_steps', 'reference_status')]:
        with panel:
            _trace_table(trace[key])
            status = trace[status_key]
            if status.get('error'):
                st.warning(str(status['error']))
            if status.get('truncated'):
                st.caption('Trace capped at 100 events; later states were not recorded.')
    st.caption('Tracing is diagnostic and can change timing. Recorded locals are bounded snapshots, not tamper-proof evidence from hostile programs.')
    patch_tab, judge_tab = st.tabs(['Self-verifying one-line patch', 'Why Not Just Use ChatGPT?'])
    with patch_tab:
        st.caption('Optional AI request: sends both code versions, the reduced input, and trace to the configured provider. Every candidate is rechecked on the original suite plus the reduced input.')
        if st.button('Generate and verify a one-line patch', disabled=stale):
            try:
                provider = _provider()
                suite = list(dict.fromkeys(bundle['inputs'] + [bundle['failing_input']]))
                with st.spinner('Proposing and checking a patch (up to three proposals)…'):
                    st.session_state.verified_patch = generate_verified_patch(
                        bundle['student'], bundle['reference'], bundle['failing_input'], trace,
                        lambda code: check_suite(code, bundle['reference'], suite), llm=provider)
            except Exception as exc:
                st.session_state.verified_patch = {'is_verified': False, 'error': str(exc)}
        patch = st.session_state.get('verified_patch')
        if patch:
            if patch['is_verified']:
                badge = '✅ Verified in Sandbox' if patch['sandboxed'] else '✅ Verified by process-limited runner (OS sandbox unavailable)'
                st.success(f"{badge}: {patch['passed_count']}/{patch['total_count']} supplied tests passed (100%).")
                st.caption('Finite-suite verification, not a guarantee of correctness on all inputs.')
            else:
                st.warning('Unverified: ' + patch.get('error', 'No patch passed the test suite.'))
            if patch.get('diff_text'):
                st.code(patch['diff_text'], language='diff')
                st.write(patch['explanation'])
                st.download_button('Download proposed patch', patch['patched_code'], 'patched.py', mime='text/x-python')
    with judge_tab:
        st.caption('A comparison of evidence, not a claim that AI always guesses incorrectly. Only student code is sent for the blind guess; the intended problem may be ambiguous.')
        if st.button('Ask AI for a blind guess', disabled=stale):
            try:
                with st.spinner('Requesting an unverified code-only guess…'):
                    st.session_state.blind_guess = guess_failing_case(bundle['student'], llm=_provider())
            except Exception as exc:
                st.session_state.blind_guess = {'error': str(exc)}
        guess_panel, proof_panel = st.columns(2)
        with guess_panel:
            st.markdown('**Blind AI · unverified prediction**')
            guess = st.session_state.get('blind_guess')
            if not guess:
                st.caption('No AI request made yet.')
            elif guess.get('error'):
                st.info(guess['error'])
            else:
                st.code(guess['input'], language='text')
                st.write('Guessed expected output:')
                st.code(guess['expected_output'], language='text')
                st.write('Guessed program output:')
                st.code(guess['actual_output'], language='text')
                st.write(guess['explanation'])
                st.warning('Not executed. This guess may be correct, incorrect, or invalid.')
        with proof_panel:
            st.markdown('**CaseCracker · reproduced execution**')
            st.code(bundle['failing_input'], language='text')
            st.write('Reference output:')
            st.code(shrink['expected'] if shrink['is_failure'] else bundle['failure']['expected'], language='text')
            st.write('Observed student output / error:')
            st.code((shrink['actual'] or shrink['error']) if shrink['is_failure'] else (bundle['failure']['actual'] or bundle['failure']['error']), language='text')
            st.caption('OS sandbox active.' if bundle['failure']['sandboxed'] else 'Process-limited execution; OS sandbox unavailable on this host.')
