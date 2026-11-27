# ClipFlow roadmap and acceptance gates

Follow **ROADMAP → TASK → ACCEPTANCE CRITERIA → INSPECT → EXECUTE → TEST**. A design, static check, or unit test never implies production acceptance.

| Gate | Task | Acceptance evidence | Status |
| --- | --- | --- | --- |
| CF-P0 | Publish sanitized engineering scaffold, dashboard preview, automated offline checks | Exactly 2 inactive n8n workflows; zero checked-in secrets; local demo reachable only on loopback; offline tests pass | Offline qualification completed; remote GitHub release pending |
| CF-P1A | Isolated identity, Neon schema, command API, Telegram poller | Signed actor/chat allowlist, duplicate command suppression, actual authenticated Neon migration, concurrent transaction tests | NOT IMPLEMENTED |
| CF-P1B | Local STT/FFmpeg worker, Google Drive, Telegram draft delivery | Footage rights verified; H.264 vertical QA; hash and Drive readback; Telegram receipts; 50 MB boundary tests | NOT IMPLEMENTED |
| CF-P2A | Publishing retry and ambiguous-result recovery | 5 automatic retries globally per finished video, separately retained platform successes, no duplicate send after uncertain response | Offline contract only |
| CF-P2B | Scoped 7-day retention | 168-hour boundary; owner+folder+project marker checks; dry-run; holds; Drive absence readback; FK-safe Neon cleanup | Offline contract only |
| CF-P2C | Live dashboard | Secure server-side auth; least-privilege read queries; incident data, storage and retry truth; no direct client Neon credentials | Synthetic demo only |
| CF-P3 | Authorized YouTube/TikTok publishing | OAuth scopes, provider eligibility and account-level consent; safe sandbox tests; verification of publish outcomes | BLOCKED |
| CF-P4 | Host soak and operational acceptance | Measured load, crash recovery, resource constraints, quota handling, 24-hour unattended observation | NOT RUN |

## Hard stop conditions

- Never clip footage solely because it appears in YouTube trending search; own or licensed use must be verified.
- Never push `.env` files, OAuth tokens, actual Drive IDs, private media, API dumps or production logs to public GitHub.
- Never execute remote deletion until an isolated account and exact ownership/authorization gates are satisfied.
- Never claim TikTok public posting works before official access and policy qualification.
- Never expose the synthetic dashboard server on a public listener; the preview has no user authentication.

## Release procedure

1. Prepare the public source package with secret-scan and test evidence.
2. Create an empty **public** GitHub repository in the intended GitHub account.
3. Commit only reviewed source files, documentation, example env variables and fictional fixture data.
4. Read back the published commit and CI result. Do not mark GitHub publishing PASS until this step is actually observed.
5. Keep project-specific implementation handoffs, internal account IDs and service credentials in a separate private records location.
