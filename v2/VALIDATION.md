# Validation — 25 September 2026

- Python 3.14. Streamlit 1.58.0, LangGraph 1.2.11.
- Automated suite: 14 passed, including Streamlit AppTest profile → watchlist → refresh → dashboard → alert acknowledgement, persistence and duplicate prevention.
- Live Greenhouse check: Stripe returned 692 jobs. First returned job was Abuse Investigator with 4,566 characters of extracted description. Counts change over time.
- Running Streamlit verified in the in-app browser at http://127.0.0.1:8502. Empty state and demo dashboard rendered. Adjusted card widths after visual review to prevent score truncation.
- Lever and generic JSON-LD tested with controlled fixtures; not verified against every live company. End-to-end UI tests use a controlled discovery result for reproducibility; real network validation was a separate feed check.
- No outbound notifications, applications or scheduled tasks created.
- No personal profile prefilled. No real user resume used in tests. Original Desktop project left unchanged; v2 delivered as a separate upgrade package.

## Notification and publishing update — 25 September 2026

- Notification settings support email, WhatsApp or both, with test sends and optional sending of new alerts after manual refresh.
- Delivery history records provider acceptance or unknown status; duplicate submission is prevented per alert and channel.
- 18 automated tests passed, including provider configuration, delivery deduplication and ambiguous failure handling. Provider calls were mocked: no email or WhatsApp was sent during tests.
- Hosted access locks when a non-local host is used without `CAREERPILOT_APP_PASSWORD`.
- Git ignores local secrets and personal SQLite data. The deployment guide describes Streamlit Cloud storage limits.
