# CareGuide AI — Healthcare Symptom-Triage FAQ Bot

Academic end-term project prototype.

## What it does
- Conversational symptom intake
- Emergency red-flag detection before the LLM
- Urgent vs routine guidance
- Strong non-diagnosis disclaimer
- Clear doctor/emergency escalation
- FAQ library
- Built-in Project Defense section containing answers to the supplied Question Bank
- Optional Gemini API enhancement; safe deterministic fallback if the API is unavailable

## Run
```bash
pip install -r requirements.txt
streamlit run app.py
```

Optional Gemini setup:
```bash
# Windows PowerShell
$env:GEMINI_API_KEY="YOUR_KEY"
streamlit run app.py
```

Or create `.env`/environment variables through your deployment platform.

## Deployment
Recommended: Streamlit Community Cloud or another Python web host. Set `GEMINI_API_KEY` as a server-side secret; never paste a production API key into frontend JavaScript or commit it to GitHub.

## Important scope
This is an academic prototype. It is not clinically validated, does not diagnose, and should not be used as a substitute for professional medical care.
