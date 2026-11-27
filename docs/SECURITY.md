# Security and rights policy

- **Dedicated accounts:** do not reuse personal Drive, Neon databases, Telegram bots, or credentials from other projects.
- **No secrets in Git:** `.env`, service account keys, OAuth refresh tokens, uploaded clips, source footage, database dumps, and operational logs remain private.
- **No public dashboard:** the preview binds to `127.0.0.1` and contains fictional values. The future live dashboard needs owner authentication, short sessions, and a backend that enforces least privilege.
- **Sources:** discovering a video via YouTube does not grant reuse rights; production requires owned or licensed source video verification.
- **Publishing:** official account-level OAuth and user consent are required. No session-cookie automation or circumvention of TikTok or YouTube restrictions.
- **Telegram ingress:** verify both sender ID and chat ID, use HMAC and deduplicate updates durably. Store an ambiguous network outcome as unknown.
- **Retention:** no destructive cleanup until the dedicated Drive owner, parent folders, project marker and exact file identity are verified. Hold unresolved work indefinitely until cleared. Keep a minimal tombstone for incident recovery.
- **Public contributions:** redact IDs, hashes derived from sensitive assets, personal filenames, emails, API response bodies and actual video URLs. Do not submit third-party footage or full copyrighted transcripts.

Do not report vulnerabilities through public issues. Contact the repository maintainer privately through GitHub.
