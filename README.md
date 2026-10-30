# CaseCracker

A simple Streamlit interface for entering a problem and Python solution, with a
results panel and an optional, clearly labeled temporary sample preview.

## Run locally

Requires Python 3.10 or newer.

```sh
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

## Integration status

**No submitted code is executed. No AI provider or execution runner is connected.**
The default button reports this status. Selecting the sample checkbox displays
fixed illustrative data unrelated to the submitted solution, not a real result.

- `app.py`: Streamlit UI and input validation.
- `casecracker/ai.py`: AI test suggestion boundary (currently a stub).
- `casecracker/execution.py`: execution boundary (currently a stub).
- `casecracker/models.py`: shared result types.
- `casecracker/samples.py`: explicitly synthetic preview data.

To integrate real testing, connect an AI provider and an isolated, resource-limited
runner through these modules. Only report execution after receiving actual runner
results, and only report a failing test after checking output against a trusted
expected answer.
