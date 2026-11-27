# ClipFlow public engineering handoff v0.6

Date: 2026-11-27  |  Track: P0 offline qualification and public-source preparation

## ROADMAP → TASK → ACCEPTANCE CRITERIA → INSPECT → EXECUTE → TEST

- **Roadmap:** exactly two n8n workflows, isolated Neon metadata, isolated dedicated Drive, Telegram commands/preview, local clip worker, future authorized publishing, seven-day safe cleanup, authenticated read-only dashboard.
- **Task completed:** assembled the open-source P0 engineering scaffold, wrote a runnable local synthetic dashboard frontend and HTTP server, added offline tests and CI, documented security boundary and non-production gaps.
- **Acceptance criteria:** documented architecture; two inactive workflow JSONs; no public secrets or live media; dashboard loopback-only; tested simulated user controls; no real deletion or publishing.
- **Inspect:** no existing ClipFlow GitHub repository found through the linked account; the currently available GitHub integration cannot create a repository. This handoff does **not** assert that the source was published.
- **Execute:** created local public-ready release with `.gitignore`, MIT license, docs, workflow scaffolds, Python contracts, synthetic dashboard, offline CI.
- **Test:** 70/70 offline Python tests passed; `node --check dashboard/public/app.js` passed; browser simulation loaded all six dashboard views and filtered search with no JavaScript errors. Browser test used an in-memory synthetic fixture, not live HTTP integrations. No external systems were modified.

## Release prerequisites

1. Create an **empty public** `ClipFlow` repository under the intended GitHub account (without README/license/gitignore initialization), or make an existing public repository available to the GitHub connector.
2. Complete a last-mile diff and secret review before the first commit. Commit only files from the public-ready package.
3. Verify the GitHub main branch readback and offline CI status after publishing.
4. Connect dedicated project Google/Telegram/Neon identities before implementation; no credentials in GitHub.

## Next engineering gate

CF-P1A-001: develop real authenticated commands API, isolated Neon schema and job leases; verify two n8n workflows import cleanly. CF-P1B: video processing worker and private Drive/Telegram delivery. CF-P2: retry/exactly-once-style safeguards, recovery, cleanup. CF-P3: official publishing. CF-P4: measured soak and operational acceptance.

No source from third-party YouTube videos may be clipped without verified reuse rights. Public TikTok publication remains disabled until policy and authorization qualification.
