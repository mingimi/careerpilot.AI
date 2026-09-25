# CareerPilot AI

CareerPilot AI is a competition-ready Streamlit MVP for personalized job discovery. It uses a LangGraph career manager to coordinate specialist agents that turn a resume and preferences into role recommendations, source-agnostic job matches, a tailored resume draft, skill-gap actions, interview prep, and a human-approved application package.

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate       # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
streamlit run app.py
```

The app works without API keys using mock job data. For live public search, copy `.env.example` to `.env` and export `TAVILY_API_KEY` before starting Streamlit. LinkedIn is not required. Live search results are normalized into the same structured job schema as the mock data, so providers can be swapped without changing the UI.

## Architecture

```mermaid
flowchart LR
  UI[Streamlit UI] --> M[Career Manager\nLangGraph shared state]
  M --> P[Career Profile Agent]
  P --> R[Role Recommendation Agent]
  R --> D[Job Discovery Agent\nTavily / public sources / mock fallback]
  D --> J[Job Match Agent]
  J --> T[Resume Tailoring Agent]
  T --> G[Skill Gap Agent]
  G --> I[Interview Prep Agent]
  I --> A[Application Agent\napproval gate + prepared fallback]
```

## Agent contract

Every node reads and returns the shared `CareerState`: resume text, preferences, structured profile, recommendations, jobs, match scores, tailored resume, skill gaps, interview prep, application state, and an activity log. The application agent never submits automatically; it prepares materials and requires explicit user approval.

## Demo notes

- Upload PDF, DOCX, or TXT resumes.
- If parsing fails, the app still demonstrates the full workflow using preferences and fallback profile skills.
- `MOCK_JOBS` in `app.py` is deliberately source-agnostic and can be replaced with an API adapter.
- No credentials are committed. Keep keys in environment variables.
