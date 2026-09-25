# Email and WhatsApp setup

CareerPilot can send queued high-match job alerts when you press **Send pending alerts**, or send newly queued alerts after a manual **Refresh watchlist** if you enable that option. It does not scan in the background. Select email, WhatsApp or both in Notifications. The test buttons send a connection test to the saved destination.

## Credentials

Create `.streamlit/secrets.toml` locally or add the same values in your Streamlit Community Cloud app's **Advanced settings → Secrets**. This file is ignored by Git. Do not paste credentials into GitHub, chat or the Streamlit public interface.

For email, use an SMTP account. Gmail requires a Google app password, not your usual login password:

```toml
SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = "465"
SMTP_USERNAME = "you@gmail.com"
SMTP_PASSWORD = "your-app-password"
SMTP_FROM = "you@gmail.com"
```

For WhatsApp, use Twilio WhatsApp Sandbox for testing or an approved WhatsApp Business sender for production:

```toml
TWILIO_ACCOUNT_SID = "AC..."
TWILIO_AUTH_TOKEN = "..."
TWILIO_WHATSAPP_FROM = "+14155238886"
TWILIO_CONTENT_SID = "HX..."
```

Confirm the sender number displayed in **your** Twilio console. Your own destination goes in CareerPilot's Notifications settings in E.164 format, such as `+919876543210`. Join the Twilio Sandbox from that destination number before testing. The destination must be opted in.

**WhatsApp rule:** Free-form messages generally require a user-initiated 24-hour service window. For proactive alerts outside that window, create an approved Twilio/WhatsApp content template and set `TWILIO_CONTENT_SID`. Template variables: `{{1}}` job title, `{{2}}` company, `{{3}}` score, `{{4}}` listing link. Twilio messaging can incur charges. The template must be approved for the relevant category/region.

## Delivery behavior

- Only role, company, fit score and listing link are transmitted; your resume is never included.
- Each alert/channel pair is submitted at most once. Up to 10 submissions per batch limit cost and request time.
- Provider acceptance is recorded as **accepted**; it does not prove inbox or handset delivery.
- Ambiguous failures are recorded **unknown** and never retried automatically, because the provider may have accepted the request before a timeout. Check provider logs before any manual retry.
- Enable **Send new alerts after I refresh the watchlist** to send newly queued alerts when you manually refresh. Existing alerts can be sent with **Send pending alerts**.
- The local database keeps delivery history. Hosted Streamlit storage can reset; durable storage is needed for dependable deduplication and scheduled monitoring.

Provider references: [Twilio WhatsApp quickstart](https://www.twilio.com/docs/whatsapp/quickstart), [Twilio template guidance](https://www.twilio.com/docs/whatsapp/tutorial/send-whatsapp-notification-messages-templates), [Google app passwords](https://support.google.com/accounts/answer/185833).

## Hosted access

CareerPilot requires `CAREERPILOT_APP_PASSWORD` in Streamlit secrets when reached through a non-local host. Add a long unique password before entering your real resume. The hosted app stays locked without it. Streamlit Community Cloud also supports viewer access controls; use a private app if available. This single shared password is suitable only for a personal prototype, not multiple users. Hosted SQLite files can reset on app restarts, so do not depend on Cloud for durable alert history.
