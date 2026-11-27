-- NOT APPLIED. Execute only against newly designated, separate ClipFlow Neon project.
-- PostgreSQL 17+; no integration with ABiz, DentalFlow or SecretaryFlow.
BEGIN;
CREATE SCHEMA IF NOT EXISTS clipflow;
CREATE TABLE IF NOT EXISTS clipflow.telegram_updates (
  update_id bigint PRIMARY KEY,
  chat_id bigint NOT NULL,
  sender_id bigint NOT NULL,
  command text NOT NULL,
  outcome text NOT NULL DEFAULT 'accepted' CHECK (outcome IN ('accepted','rejected','processed','failed')),
  received_at timestamptz NOT NULL DEFAULT now(),
  processed_at timestamptz
);
CREATE TABLE IF NOT EXISTS clipflow.trend_snapshots (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  video_id text NOT NULL CHECK (video_id ~ '^[A-Za-z0-9_-]{11}$'),
  region text NOT NULL CHECK (region ~ '^[A-Z]{2}$'),
  category text NOT NULL,
  title text NOT NULL,
  channel text,
  published_at timestamptz,
  view_count bigint NOT NULL CHECK (view_count >= 0),
  chart_position integer NOT NULL CHECK (chart_position BETWEEN 1 AND 50),
  observed_at timestamptz NOT NULL DEFAULT now(),
  raw jsonb NOT NULL DEFAULT '{}'::jsonb
);
CREATE INDEX IF NOT EXISTS trend_snapshots_trajectory ON clipflow.trend_snapshots(video_id, region, observed_at DESC);
CREATE TABLE IF NOT EXISTS clipflow.sources (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  filename text NOT NULL UNIQUE CHECK (filename ~ '^[A-Za-z0-9][A-Za-z0-9_.-]{0,125}\.(mp4|mov|mkv|webm)$'),
  drive_path text NOT NULL UNIQUE,
  rights_basis text NOT NULL CHECK (rights_basis IN ('owned','licensed')),
  rights_asserted_by bigint NOT NULL,
  rights_asserted_at timestamptz NOT NULL DEFAULT now(),
  rights_proof text,
  source_sha256 text CHECK (source_sha256 IS NULL OR source_sha256 ~ '^[a-f0-9]{64}$'),
  state text NOT NULL DEFAULT 'pending_verification' CHECK (state IN ('pending_verification','approved','blocked','revoked')),
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS clipflow.clip_jobs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  source_id uuid NOT NULL REFERENCES clipflow.sources(id),
  requested_update_id bigint NOT NULL REFERENCES clipflow.telegram_updates(update_id),
  idempotency_key text NOT NULL UNIQUE,
  state text NOT NULL DEFAULT 'queued' CHECK (state IN (
    'queued','processing','retry','rendered','drive_uploaded','delivered','failed','blocked')),
  attempts smallint NOT NULL DEFAULT 0 CHECK (attempts BETWEEN 0 AND 10),
  next_attempt_at timestamptz NOT NULL DEFAULT now(),
  leased_by text,
  lease_until timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  error_code text,
  error_summary text
);
CREATE INDEX IF NOT EXISTS clip_jobs_claimable ON clipflow.clip_jobs(next_attempt_at,created_at)
  WHERE state IN ('queued','retry');
CREATE TABLE IF NOT EXISTS clipflow.outputs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  job_id uuid NOT NULL REFERENCES clipflow.clip_jobs(id),
  clip_number smallint NOT NULL CHECK (clip_number BETWEEN 1 AND 10),
  start_sec numeric(10,3) NOT NULL CHECK (start_sec >= 0),
  end_sec numeric(10,3) NOT NULL CHECK (end_sec > start_sec),
  drive_file_id text,
  private_drive_path text,
  sha256 text CHECK (sha256 IS NULL OR sha256 ~ '^[a-f0-9]{64}$'),
  telegram_message_id bigint,
  telegram_delivery_state text NOT NULL DEFAULT 'pending' CHECK (telegram_delivery_state IN (
    'pending','sending','sent','unknown','failed')),
  qa jsonb NOT NULL DEFAULT '{}'::jsonb,
  UNIQUE(job_id,clip_number)
);
CREATE TABLE IF NOT EXISTS clipflow.alert_outbox (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  alert_key text NOT NULL UNIQUE,
  kind text NOT NULL,
  message text NOT NULL,
  state text NOT NULL DEFAULT 'pending' CHECK (state IN ('pending','sending','sent','unknown')),
  telegram_message_id bigint,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS clipflow.audit_events (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  job_id uuid REFERENCES clipflow.clip_jobs(id),
  event_type text NOT NULL,
  event_detail jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);
-- Atomic row-claim contract. The runtime role needs execute plus scoped table grants.
CREATE OR REPLACE FUNCTION clipflow.claim_job(p_worker text, p_lease_seconds integer DEFAULT 900)
RETURNS SETOF clipflow.clip_jobs LANGUAGE sql SECURITY INVOKER SET search_path = pg_catalog,clipflow AS $$
  UPDATE clipflow.clip_jobs AS j
  SET state = 'processing', attempts = attempts + 1, leased_by = p_worker,
      lease_until = now() + make_interval(secs => least(greatest(p_lease_seconds,60),3600)),
      updated_at = now()
  FROM (
    SELECT id FROM clipflow.clip_jobs
    WHERE state IN ('queued','retry') AND next_attempt_at <= now() AND attempts < 3
    ORDER BY created_at, id FOR UPDATE SKIP LOCKED LIMIT 1
  ) AS target
  WHERE j.id = target.id
  RETURNING j.*;
$$;
-- A separate sweeper must requeue *expired* leases, and terminally fail attempts >= 3.
-- Do not blindly retry Telegram sends left in 'sending' (outcome is unknown).
COMMIT;
