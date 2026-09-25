# Publish CareerPilot v2

The repository is [mingimi/careerpilot.AI](https://github.com/mingimi/careerpilot.AI). V2 lives in `v2/`, preserving the original app at the repository root.

## Streamlit Community Cloud

1. Sign in to [Streamlit Community Cloud](https://share.streamlit.io/) with the GitHub account connected to `mingimi/careerpilot.AI`.
2. Select **Create app → Deploy a public app from GitHub** (or choose a private app if your account supports it). Repository: `mingimi/careerpilot.AI`; branch: `main`; main file: `v2/app.py`.
3. Before using personal data, open **Advanced settings → Secrets** and add a long, unique `CAREERPILOT_APP_PASSWORD`. Without this secret, the hosted app remains locked.
4. Add SMTP/Twilio secrets in the same settings if you want email or WhatsApp delivery. Follow [NOTIFICATIONS.md](NOTIFICATIONS.md). Use no real credentials in GitHub files.
5. Deploy, open the app, unlock it and test a fictional demo job. Add your profile only after checking access settings.

`v2/requirements.txt` lists Python dependencies. `.streamlit/secrets.toml` and `data/` are excluded from Git. `secrets.toml.example` is a template with placeholders only.

## Limits and next step for reliable alerts

The hosted SQLite database is stored in the app container. Streamlit Community Cloud may recreate that container after a restart or redeployment, losing profiles, watchlists, jobs, and delivery history. The app currently refreshes only when you press **Refresh watchlist**; it does not monitor companies while closed. For reliable scheduled email/WhatsApp alerts, replace the local database with a durable hosted database and run a scheduled job outside the Streamlit web process. Avoid repeatedly enabling delivery after a storage reset, because previously sent jobs may look new again.

The repository source is public. The app has one shared profile/database, so use a private app or keep its password private. It is a personal prototype, not a multi-user product.

Provider setup: [Streamlit deploy guide](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy), [Streamlit secrets](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/secrets-management).
