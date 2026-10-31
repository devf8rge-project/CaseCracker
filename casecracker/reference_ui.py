"""Generate a sample-checked AI reference without treating AI as an oracle."""
import streamlit as st

from casecracker.ai_helper import generate_reference_solution
from casecracker.checker import validate_reference_samples
from casecracker.execution import extract_test_cases_from_problem
from casecracker.proof_ui import _provider


def known_samples():
    samples = [{'input': t.input, 'expected_output': t.expected_output}
               for t in extract_test_cases_from_problem(st.session_state.get('problem', ''))]
    samples.extend({'input': t.get('input', ''), 'expected_output': t['expected_output']}
                   for t in st.session_state.get('test_cases', []) if t.get('expected_output', '').strip())
    return [dict(input=i, expected_output=o) for i, o in
            dict.fromkeys((t['input'], t['expected_output']) for t in samples)]


def generated_reference_is_stale():
    saved = st.session_state.get('generated_reference')
    return bool(saved and saved['reference_code'].strip() == st.session_state.get('reference_code', '').strip()
                and (saved['problem'] != st.session_state.get('problem', '').strip()
                     or saved['samples'] != known_samples()))


def render_reference_generator():
    st.caption('No reference code? AI can write a candidate from the full problem statement. '
               'Add examples with known expected outputs so it can be checked before use. '
               'Your student code is not sent for this request.')
    if st.button('Generate reference from problem', disabled=not st.session_state.get('problem', '').strip()):
        try:
            samples = known_samples()
            if not samples or len(samples) > 20:
                raise ValueError('Add 1–20 examples with known expected outputs first. AI guesses cannot serve as independent checks.')
            with st.spinner('Writing a reference and checking it against known examples…'):
                candidate = generate_reference_solution(st.session_state.problem.strip(), llm=_provider())
                report = validate_reference_samples(candidate['reference_code'], samples)
            st.session_state.reference_generation_attempt = {**candidate, 'report': report}
            if report['samples_passed']:
                st.session_state.reference_code = candidate['reference_code']
                st.session_state.generated_reference = {**candidate, 'report': report,
                                                        'problem': st.session_state.problem.strip(), 'samples': samples}
                for key in ('result', 'proof_bundle', 'verified_patch', 'blind_guess'):
                    st.session_state.pop(key, None)
        except Exception as exc:
            st.session_state.pop('reference_generation_attempt', None)
            st.error(f'Reference generation unavailable: {exc}')
    attempt = st.session_state.get('reference_generation_attempt')
    if attempt and not attempt['report']['samples_passed']:
        st.warning('Generated candidate failed known examples and was not applied. Your existing reference was kept.')
        st.code(attempt['reference_code'], language='python')
        for case in attempt['report']['cases']:
            if not case['passed']:
                st.write({'input': case['input'], 'expected': case['expected'],
                          'actual': case['actual'], 'error': case['error']})
    saved = st.session_state.get('generated_reference')
    if saved and saved['reference_code'].strip() == st.session_state.get('reference_code', '').strip():
        if generated_reference_is_stale():
            st.warning('Problem or examples changed. Generate the reference again before running reference analysis.')
        else:
            report = saved['report']
            st.info(f"AI-generated reference · {report['passed_count']}/{report['total_count']} known examples passed in the runner. "
                    'Used for comparisons below; correctness on other inputs is not established.')
            st.write(saved['explanation'])
