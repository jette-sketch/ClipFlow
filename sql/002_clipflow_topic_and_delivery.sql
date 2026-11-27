-- CF-P0-003: UNAPPLIED DRAFT; target only a NEW isolated ClipFlow Neon database.
-- Apply AFTER 001_clipflow_initial.sql during P1 acceptance gate.
BEGIN;
CREATE TABLE IF NOT EXISTS clipflow.topic_search_requests (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  requested_update_id bigint NOT NULL UNIQUE REFERENCES clipflow.telegram_updates(update_id),
  requested_topic text NOT NULL CHECK (length(requested_topic) BETWEEN 2 AND 80),
  canonical_topic text NOT NULL,
  scope_key text NOT NULL,
  youtube_query text NOT NULL,
  region text NOT NULL CHECK (region IN ('PH','US','GB','CA','AU')),
  state text NOT NULL DEFAULT 'queued' CHECK (state IN ('queued','searching','completed','failed')),
  created_at timestamptz NOT NULL DEFAULT now(),
  completed_at timestamptz
);
CREATE TABLE IF NOT EXISTS clipflow.topic_video_candidates (
  request_id uuid NOT NULL REFERENCES clipflow.topic_search_requests(id),
  video_id text NOT NULL CHECK (video_id ~ '^[A-Za-z0-9_-]{11}$'),
  title text NOT NULL,
  published_at timestamptz NOT NULL,
  view_count bigint NOT NULL CHECK (view_count >= 0),
  estimated_views_per_hour numeric(20,2) NOT NULL CHECK (estimated_views_per_hour >= 0),
  scope_pass boolean NOT NULL CHECK (scope_pass = true),
  signal text NOT NULL DEFAULT 'age_normalized_view_proxy_not_verified_velocity',
  observed_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY(request_id, video_id)
);
ALTER TABLE clipflow.outputs
  ADD COLUMN IF NOT EXISTS file_size_bytes bigint CHECK (file_size_bytes > 0),
  ADD COLUMN IF NOT EXISTS drive_view_url text,
  ADD COLUMN IF NOT EXISTS drive_upload_verified boolean NOT NULL DEFAULT false,
  ADD COLUMN IF NOT EXISTS recipient_access_verified boolean NOT NULL DEFAULT false,
  ADD COLUMN IF NOT EXISTS telegram_delivery_mode text
    CHECK (telegram_delivery_mode IN ('telegram_video','drive_link_only'));
-- Runtime sets these booleans after Drive files.get, hash or size readback,
-- and permission validation for the recipient. No public "anyone" sharing.
-- UNKNOWN sends must be handled by an outbox, not blindly retried.
COMMIT;
