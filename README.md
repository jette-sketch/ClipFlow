# ClipFlow

Self-hosted, Telegram-controlled YouTube trend discovery and short-form video clipping.

> **Engineering preview, not production-ready.** This public repository is being populated from the locally verified v0.6 source package. No live integrations, automated publishing, or deletion are enabled.

## Planned architecture

- **Workflow 1:** Topic-specific YouTube trend research with Telegram command intake, including `CF look for trending GTA 6 Videos`.
- **Workflow 2:** Authorized-source clipping, draft archiving, delivery, publishing recovery, and retention orchestration.
- **Neon PostgreSQL:** Job state, trend snapshots, retries, and audits.
- **Dedicated Google Drive:** Source media, generated drafts, subtitles, and recovery copies.
- **Telegram:** Control commands, previews, and error notifications. Drafts exceeding 50,000,000 bytes are delivered as private Drive links.
- **YouTube / TikTok:** Dedicated accounts and gated publishing integration, not yet enabled.
- **Dashboard:** Local, read-only operational overview using synthetic demo data until an authenticated backend exists.

## Operational safeguards

- A shared maximum of **5 automatic publishing retries per video** across destinations; reconcile ambiguous attempts before retrying.
- Seven-day deletion eligibility for **ClipFlow-owned** disposable media only, with retention holds for unresolved work.
- No deletion of already-published YouTube or TikTok videos.
- Never publish or clip third-party content without rights or authorization.

## Qualification

The prepared local v0.6 package passed **70/70 offline tests**. These tests do not establish production readiness. Publishing and retention executors have not been validated against real services.

License: MIT. Never commit tokens, OAuth secrets, database URLs, private source videos, or personal account data.
