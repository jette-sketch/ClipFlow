# ClipFlow public engineering handoff v0.6

Date: 2026-11-27  |  Track: P0 offline qualification and public-source preparation

## ROADMAP → TASK → ACCEPTANCE CRITERIA → INSPECT → EXECUTE → TEST

- **Roadmap:** exactly two n8n workflows, isolated Neon metadata, isolated dedicated Drive, Telegram commands/preview, local clip worker, future authorized publishing, seven-day safe cleanup, authenticated read-only dashboard.
- **Task completed:** assembled the open-source P0 engineering scaffold, wrote a runnable local synthetic dashboard frontend and HTTP server, added offline tests and CI, documented security boundary and non-production gaps.
- **Acceptance criteria:** documented architecture; two inactive workflow JSONs; no public secrets or live media; dashboard loopback-only; tested simulated user controls; no real deletion or publishing.
- **Inspect:** GitHub repository created under `jette-sketch/ClipFlow` as PUBLIC; the reviewed 32-file source tree was transferred and matched by Git tree SHA (`c40ed84443b4b69bc3c55a93ed01320e89eedc0b`).
- **Execute:** created local public-ready release with `.gitignore`, MIT license, docs, workflow scaffolds, Python contracts, synthetic dashboard, offline CI, then published it to the public GitHub main branch. Moved the optional `requests` dependency import into the Telegram polling runtime to make CI offline tests independent of third-party packages.
- **Test:** 70/70 offline Python tests passed; `node --check dashboard/public/app.js` passed; browser simulation loaded all six dashboard views and filtered search with no JavaScript errors. Browser test used an in-memory synthetic fixture, not live HTTP integrations. GitHub Actions run `45947285350` passed on commit `7f661f841fc66959288df462ef7aea10793b40ad`. No n8n, Neon, Google Drive, YouTube, Telegram, or TikTok production systems were modified.

## Publication evidence and remaining prerequisites

1. **DONE:** Created public repository https://github.com/jette-sketch/ClipFlow and transferred the reviewed source, with exact Git tree comparison.
2. **DONE:** Reviewed the public release for known credential patterns and excluded real media, logs, databases, and secrets. This is not a guarantee against every secret.
3. **DONE:** Verified GitHub source readback and a successful offline CI run on source commit `7f661f8`.
4. **PENDING:** Connect dedicated project Google/Telegram/Neon identities before implementation, keeping credentials out of GitHub.
5. **PENDING:** Verify actual n8n host, live integrations, and authorization / destructive-action gates before deployment.

## Next engineering gate

CF-P1A-001: develop real authenticated commands API, isolated Neon schema and job leases; verify two n8n workflows import cleanly. CF-P1B: video processing worker and private Drive/Telegram delivery. CF-P2: retry/exactly-once-style safeguards, recovery, cleanup. CF-P3: official publishing. CF-P4: measured soak and operational acceptance.

No source from third-party YouTube videos may be clipped without verified reuse rights. Public TikTok publication remains disabled until policy and authorization qualification.
