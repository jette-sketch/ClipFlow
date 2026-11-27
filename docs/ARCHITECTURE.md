# ClipFlow architecture (proposed, 2026-11-27)

```text
Dedicated Telegram bot -> authenticated private poller -> n8n workflow 01
   -> authenticated ClipFlow command API (NOT IMPLEMENTED)
      -> official YouTube research -> Neon trend records -> Telegram summary
      -> approved-source clip enqueue

n8n workflow 02 (dispatch and 03:15 PHT retention schedules)
   -> authenticated ClipFlow internal API (NOT IMPLEMENTED)
      -> Neon atomic job lease -> local transcription/highlights -> FFmpeg
      -> ffprobe validation -> dedicated Drive draft readback
      -> Telegram MP4 if <= 50,000,000 bytes, else private Drive link
      -> separate guarded YouTube/TikTok publication state machines
      -> error reconciliation, 5 shared retry reservations, alerts
      -> scoped 168-hour retention with dry-run and audit tombstones

Dashboard: localhost-only read-only HTTP -> backend snapshot endpoint (FUTURE)
           Current implementation: synthetic JSON fixture only
```

Only two n8n workflows; all other components are services/scripts.

### State consistency

- Neon is the source of truth for job claims, retry reservation, deduplication, and audit references.
- Do not store video BLOBs or credentials in Neon. Drive holds private media under a dedicated identity.
- Files are uploaded and hash-checked before delivery or publication. Failed uploads retain archived drafts.
- Unknown delivery outcomes must be reconciled before resend to avoid duplicates.
- Drive deletion must be scoped to verified owner and project marker, followed by readback, then FK-safe Neon cleanup.
- Successful YouTube publication never gets reset because TikTok failed, or vice versa.
- Dashboard is read-only. Any future control actions must go through the backend's authorization and auditing, not browser-side SQL.

### API status

`/v1/commands`, `/v1/dispatch`, `/v1/retention/sweep`, and a real `/api/v1/dashboard` snapshot endpoint are **not** implemented. Existing workflow JSON is structural scaffolding and **inactive**. This repository alone cannot perform real unattended clipping or automatic publishing.
