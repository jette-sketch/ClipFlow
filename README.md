# ClipFlow

**Self-hosted, Telegram-controlled YouTube trend discovery and short-form video clipping.**

> **Engineering preview, not production-ready.** The two inactive n8n workflow definitions and offline validation contracts are provided for development. The local operations dashboard uses **fictional synthetic data**, and no external accounts are connected by this repository. Do **not** activate publishing or deletion jobs based solely on this scaffold.

## Architecture

| Component | Responsibility |
| --- | --- |
| n8n workflow 01 | Private webhook command intake and topic-specific YouTube research |
| n8n workflow 02 | Media dispatch and scheduled seven-day retention request |
| ClipFlow backend (not yet implemented) | Auth, command dedupe, transactional job queue, upload recovery, cleanup executor |
| Neon PostgreSQL | Job state, trend snapshots, retries and sanitized audit metadata |
| Dedicated Google Drive | Private source files, draft videos, captions and thumbnails |
| Dedicated Telegram bot | Commands, draft preview delivery, failure alerts |
| Local STT + FFmpeg (not integrated) | Transcription, clip selection, vertical rendering and validation |
| Dedicated YouTube / TikTok identities | Publishing integrations, **disabled pending eligibility and consent** |
| Dashboard | Loopback-only, read-only operations preview; synthetic data until backend exists |

**Exactly two n8n workflows.** The Telegram poller and clipping worker are separate processes, not additional n8n workflows.

## Planned command and safety contracts

- `CF look for trending GTA 6 videos`: research videos about GTA 6 only, with `Grand Theft Auto VI` treated as an alias. Irrelevant GTA 5 results must be rejected.
- `/trending PH gaming`: official chart research, not necessarily current viral growth.
- `/clip <approved-source-id>`: render only footage that is authorized for reuse.
- `/status`: check jobs, alerts and delivery states.
- For draft files **larger than 50,000,000 bytes**, Telegram receives only a **private Google Drive link**; at or below that size it can receive the MP4, with Drive-link fallback on Telegram error.
- **Five automatic retries per finished video, shared across its two publication destinations**, not five per destination. Ambiguous uploads require reconciliation, not blind resend.
- **Retention: seven full days** for eligible project-owned media and temporary metadata, with holds for unresolved uploads, incidents and rights. No YouTube/TikTok published content is deleted.

**Important:** The above are design and offline contract requirements, **not verified end-to-end integrations**.

## Run the local dashboard demonstration

Requires Python 3.11+ (standard library only):

```bash
python dashboard/server.py --port 8765
```

Open `http://127.0.0.1:8765`. The dashboard is **read-only** and always returns `mode: synthetic_demo, connected: false`. It binds only to `127.0.0.1`. No authentication is provided because this is a local demonstration. Do not expose it on a public host or tunnel.

The six views are Overview, Trend Hunter, Production, Publishing, Storage & Retention, and System Health.

## Offline checks

```bash
python -m unittest discover -s tests -v
node --check dashboard/public/app.js
```

The test suite does not connect to n8n, Neon, Telegram, YouTube, TikTok or Google Drive. Passing tests are **not** a deployment approval.

## Setup prerequisites for actual implementation

1. Provision a dedicated project email and Google Drive, not an existing personal or company Drive.
2. Provision a separate Neon project and least-privilege runtime identity.
3. Set up a dedicated Telegram bot and pin an allowed `chat_id` and `user_id`.
4. Verify official YouTube Data API quota and publication account capabilities.
5. Obtain required TikTok application approval / provider eligibility. No cookie scraping or browser-bot publishing.
6. Implement the authenticated internal backend endpoints and worker before importing/activating n8n workflows.
7. Run a protected, read-only seven-day retention dry run, then qualify one explicitly authorized disposable deletion.

Copy `.env.example` to `.env` **locally**, keep it out of Git, and provision real tokens through an approved secret store or n8n credentials. **Never open-source bot tokens, OAuth credentials, Drive file IDs, Neon connection strings, client video assets, or actual job logs.**

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md), [`docs/SECURITY.md`](docs/SECURITY.md), [`docs/STATUS.md`](docs/STATUS.md), and [`HANDOFF_v0.6.md`](HANDOFF_v0.6.md) for design gates.

## Open source

MIT licensed. Contributions are welcome for offline tests, documentation, and isolated software components. Public pull requests must not introduce copyrighted third-party video, credentials or automatic publishing without a clear rights and authorization model.
