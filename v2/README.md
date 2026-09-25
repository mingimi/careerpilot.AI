# CareerPilot AI v2

Upgrade of your existing Streamlit + LangGraph project. Includes profile/resume ingestion, company watchlist, live public job discovery, normalized JDs, explained matching, dashboard and optional email/WhatsApp alert delivery. No API key is required for job discovery; sending requires provider credentials.

## Run

Open this folder in VS Code. Python 3.11+ recommended.

```bash
python -m venv .venv
source .venv/bin/activate
# Windows PowerShell instead: .venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

1. **My profile:** upload PDF/DOCX/TXT or paste resume text. Review skills, enter roles, years, locations and JD keywords; save.
2. **Company watchlist:** save a company name and official careers URL. A name alone is saved but needs a URL before discovery; company identity is never guessed.
3. **Refresh watchlist:** each company reports complete-feed, partial-page or failed status.
4. **Job dashboard:** inspect score components, full extracted JD and source links.
5. **Notifications:** enable email, WhatsApp or both; test the connection, send pending alerts, optionally send new alerts after a manual refresh, inspect delivery history and mark events read.

Real source example: `https://job-boards.greenhouse.io/stripe`. The demo switch shows fictional jobs without writing them to your database.

## Upgrade provenance

Original project found at `/Users/lucky/Desktop/careerpilot-ai`. V2 retains Streamlit, the typed LangGraph CareerState/manager pattern, resume formats and selected fictional company fixtures. The original application and README are preserved in `legacy/`; credentials were not copied. The Desktop original is unchanged. Its tailoring/interview/application screens are archived, outside this focused v2 MVP. There was no v1 database to migrate.

V2 replaces invented fallback skills, baseline match scores and silent mock fallback on discovery failure with explicit evidence and source errors.

## Discovery support

- Greenhouse public Job Board API, full descriptions.
- Lever global/EU Postings API, pagination up to 2,000 jobs; exceeding the cap fails the scan.
- Career-page JobPosting JSON-LD, linked ATS detection, and up to 10 same-host job detail links.
- HTML fetching conservatively honors robots.txt. Missing/inaccessible robots files stop page scanning; direct supported ATS feeds remain an alternative.
- HTTPS, public-address and redirect checks, request timeouts and response-size limits.
- No Glassdoor, AmbitionBox, LinkedIn scraping, login bypass or auto-apply.
- JavaScript-only pages, Workday and generic unstructured HTML need future adapters. Partial scans are labelled and do not imply a full inventory.

Adapter references: [Greenhouse documentation](https://docs.greenhouse.io/job-board.html), [Lever documentation](https://github.com/lever/postings-api).

## Transparent scoring

| Dimension | Weight | Rule |
|---|---:|---|
| Role | 30 | Best target-role word overlap with title |
| Skills | 30 | Fraction of recognized JD skills in reviewed profile |
| Experience | 20 | Full if numeric minimum met, proportional otherwise |
| Location | 15 | Preferred phrase found in advertised location |
| Preferences | 5 | Fraction of preferred keywords found in JD |

Unknown evidence earns zero points, without redistributing weight. Evidence coverage shows how much could be evaluated. Scores are fit heuristics, not hiring probabilities. JD skills use a finite vocabulary and do not distinguish required/preferred mentions. Experience extraction only recognizes numeric phrases and requires review for alternatives. Remote/location matches do not establish work authorization. No salary or industry assumptions are made.

## Persistence and alerts

Local single-user SQLite at `data/careerpilot.db`; override with `CAREERPILOT_DB`. Resume text, profile, companies, jobs, timestamps and outbox survive restart.

An event queues once per newly discovered source/job identity when score meets the scan threshold (default 75) and coverage is at least 70%. The first scan counts as new discovery, not proof the employer just posted it. Rescans update JDs without repeat alerts. Profile/threshold changes do not generate retrospective alerts. Dashboard scores always recalculate. Acknowledgement means read, not externally delivered. Export JSON is the integration boundary.

Historical jobs are retained and may have closed; last-seen times are visible. Failed scans preserve saved results. Verify listings before applying. Removing a company removes its jobs and alerts; re-adding starts afresh.

## Structure

- `app.py`: Streamlit screens.
- `careerpilot/core.py`: resume parsing, normalization, deterministic scoring.
- `careerpilot/discovery.py`: public adapters and bounded HTTP client.
- `careerpilot/store.py`: SQLite and outbox.
- `careerpilot/workflow.py`: actual LangGraph orchestration and per-company failure isolation.
- `careerpilot/demo.py`: isolated fictional fixtures.
- `careerpilot/notifications.py`: opt-in provider delivery and deduplicated status records.

Future modules can add sourced interview research, evidence-based resume tailoring and application tracking by job ID. A scheduler can call `scan(Store(), threshold=75)`. There is no background scheduler in this MVP. Email and WhatsApp delivery are optional and only run when explicitly requested or after a manual refresh with automatic sending enabled. No LLM is called in this MVP. See [notification setup](NOTIFICATIONS.md).

## Test

```bash
python -m pytest -q
```

See VALIDATION.md for automated and live checks. Tests cover scoring, resume parsing, source normalization, blocked URLs, database persistence, delivery deduplication, graph fault isolation and a Streamlit profile-to-notification journey.

## Local use and deployment

Job discovery needs no paid APIs. Email needs SMTP credentials; WhatsApp needs Twilio and may incur charges. Personal resume text is stored locally without encryption. Do not commit `data/`, `.env` or `.streamlit/secrets.toml`. Deleting the database resets stored data. When reached through a non-local host, the app locks until `CAREERPILOT_APP_PASSWORD` is set in Streamlit secrets. This prototype uses one shared workspace; do not share its password with others. Streamlit Community Cloud local storage can reset on restart, so use durable hosted storage before relying on long-term notifications. See [GitHub and Streamlit deployment](DEPLOY.md).

## Two-minute presentation

Save a Growth Marketing Associate profile with Marketing, Excel and Communication. Show demo jobs and explained score gaps. Switch demo off, add a public ATS board, refresh and show the source JD. Show the outbox, then refresh again to demonstrate duplicate prevention. Explain that email and WhatsApp require provider setup, and interview intelligence is a future module.
