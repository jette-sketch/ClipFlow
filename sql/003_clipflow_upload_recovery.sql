-- P0 DRAFT ONLY, NOT APPLIED. Target ONLY isolated ClipFlow Neon project AFTER 001 and 002.
-- Scope: one aggregate retry budget for one finished video (clipflow.outputs.id),
-- shared between YouTube and TikTok. Does not alter render-job attempt budget.
-- This is a proposed database enforcement layer, not a tested production migration.
BEGIN;
CREATE TABLE IF NOT EXISTS clipflow.video_upload_budgets (
    output_id uuid PRIMARY KEY REFERENCES clipflow.outputs(id) ON DELETE CASCADE,
    retries_reserved smallint NOT NULL DEFAULT 0
      CHECK (retries_reserved BETWEEN 0 AND 5),
    updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS clipflow.platform_uploads (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    output_id uuid NOT NULL REFERENCES clipflow.outputs(id) ON DELETE CASCADE,
    platform text NOT NULL CHECK (platform IN ('youtube', 'tiktok')),
    authorization_mode text NOT NULL DEFAULT 'none' CHECK (authorization_mode IN (
      'none','youtube_private','tiktok_inbox','approved_direct_post')),
    authorized_at timestamptz,
    state text NOT NULL DEFAULT 'draft_archived' CHECK (state IN (
      'draft_archived','queued','uploading','retry_wait','reconcile_required',
      'youtube_private_uploaded','tiktok_inbox_draft','published_verified',
      'failed_terminal','retry_exhausted','integration_blocked')),
    -- Upload session URLs, OAuth access/refresh tokens and TikTok upload_url
    -- are credentials and MUST NEVER be stored here. Store only opaque secret-store refs.
    resume_secret_ref text,
    platform_video_id text,
    platform_publish_id text,
    last_error_code text,
    last_error_summary text,
    next_attempt_at timestamptz,
    last_checked_at timestamptz,
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (output_id, platform)
);
CREATE TABLE IF NOT EXISTS clipflow.upload_retry_reservations (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    output_id uuid NOT NULL REFERENCES clipflow.outputs(id) ON DELETE CASCADE,
    platform text NOT NULL CHECK (platform IN ('youtube','tiktok')),
    operation_key text NOT NULL CHECK (length(operation_key) BETWEEN 8 AND 128),
    state text NOT NULL DEFAULT 'reserved' CHECK (state IN (
      'reserved','in_flight','completed','reconcile_required','cancelled')),
    reserved_at timestamptz NOT NULL DEFAULT now(),
    finished_at timestamptz,
    UNIQUE (output_id, operation_key)
);
CREATE INDEX IF NOT EXISTS platform_uploads_due
  ON clipflow.platform_uploads(next_attempt_at, output_id)
  WHERE state IN ('queued','retry_wait');

-- Transactional reservation MUST precede every *new automatic retry*.
-- Calls for the same operation key receive 'duplicate' instead of another send.
-- 'reserved' != executed; on crashes, the runtime must recover the same
-- reservation, never reserve another for an already in-flight attempt.
CREATE OR REPLACE FUNCTION clipflow.reserve_upload_retry(
    p_output_id uuid, p_platform text, p_operation_key text)
RETURNS text LANGUAGE plpgsql SECURITY INVOKER
SET search_path = pg_catalog, clipflow AS $$
DECLARE
    v_count smallint;
    v_is_verified boolean;
    v_platform_state text;
    v_auth_mode text;
    v_authorized_at timestamptz;
BEGIN
    IF p_platform IS NULL OR p_platform NOT IN ('youtube','tiktok') THEN
        RAISE EXCEPTION 'unsupported platform';
    END IF;
    IF p_operation_key IS NULL OR length(p_operation_key) NOT BETWEEN 8 AND 128 THEN
        RAISE EXCEPTION 'invalid retry operation key';
    END IF;
    SELECT (o.drive_upload_verified AND o.recipient_access_verified AND
            o.drive_file_id IS NOT NULL AND s.state = 'approved')
      INTO v_is_verified FROM clipflow.outputs o
      JOIN clipflow.clip_jobs j ON j.id = o.job_id
      JOIN clipflow.sources s ON s.id = j.source_id
      WHERE o.id = p_output_id;
    IF v_is_verified IS DISTINCT FROM true THEN
        RETURN 'draft_unverified';
    END IF;
    INSERT INTO clipflow.video_upload_budgets(output_id) VALUES (p_output_id)
      ON CONFLICT (output_id) DO NOTHING;
    SELECT retries_reserved INTO v_count FROM clipflow.video_upload_budgets
      WHERE output_id = p_output_id FOR UPDATE;
    -- After taking row lock, check same-key duplicates before enforcing limit.
    IF EXISTS (SELECT 1 FROM clipflow.upload_retry_reservations
               WHERE output_id = p_output_id AND operation_key = p_operation_key) THEN
        RETURN 'duplicate';
    END IF;
    SELECT state, authorization_mode, authorized_at INTO v_platform_state, v_auth_mode, v_authorized_at
      FROM clipflow.platform_uploads
      WHERE output_id = p_output_id AND platform = p_platform FOR UPDATE;
    IF v_auth_mode IS NULL OR v_auth_mode = 'none' OR v_authorized_at IS NULL
       OR (p_platform = 'youtube' AND v_auth_mode NOT IN ('youtube_private','approved_direct_post'))
       OR (p_platform = 'tiktok' AND v_auth_mode NOT IN ('tiktok_inbox','approved_direct_post')) THEN
        RETURN 'publishing_not_authorized';
    END IF;
    IF v_platform_state IS DISTINCT FROM 'retry_wait' THEN
        RETURN 'not_retryable_state';
    END IF;
    IF EXISTS (SELECT 1 FROM clipflow.upload_retry_reservations
               WHERE output_id = p_output_id AND platform = p_platform
               AND state IN ('reserved','in_flight','reconcile_required')) THEN
        RETURN 'outstanding_attempt';
    END IF;
    IF v_count >= 5 THEN RETURN 'exhausted'; END IF;
    INSERT INTO clipflow.upload_retry_reservations(output_id, platform, operation_key)
      VALUES (p_output_id, p_platform, p_operation_key);
    UPDATE clipflow.video_upload_budgets
      SET retries_reserved = retries_reserved + 1, updated_at = now()
      WHERE output_id = p_output_id;
    RETURN 'reserved';
END;
$$;
-- P1 gate: role grants, concurrent transactions, lease recovery, and a readback
-- audit MUST pass before enabling this function in a live worker.
COMMIT;
