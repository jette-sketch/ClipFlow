-- ClipFlow v0.5 UNAPPLIED DRAFT. Apply AFTER 001, 002, 003 only against
-- a new dedicated ClipFlow Neon project. NOT an authorization to purge data.
-- Runtime must verify a dedicated Google account + project-scoped files before
-- permanent Drive deletion. No source or output is deleted by this migration.
BEGIN;
CREATE TABLE IF NOT EXISTS clipflow.retention_assets (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  output_id uuid REFERENCES clipflow.outputs(id) ON DELETE CASCADE,
  source_id uuid REFERENCES clipflow.sources(id) ON DELETE CASCADE,
  -- Links are exclusively to this project's account. NO shared folders.
  storage_kind text NOT NULL CHECK (storage_kind IN ('drive','local')),
  asset_kind text NOT NULL CHECK (asset_kind IN (
      'source_video','rendered_clip','subtitle','thumbnail','temp_media')),
  drive_file_id text,
  local_asset_key text,
  media_bytes bigint CHECK (media_bytes IS NULL OR media_bytes >= 0),
  -- Worker records when remote upload was verified; never trusts provider
  -- modifiedTime, user-written filenames, or client-side backdating.
  created_at timestamptz NOT NULL DEFAULT now(),
  eligible_at timestamptz NOT NULL DEFAULT (now() + interval '7 days'),
  state text NOT NULL DEFAULT 'tracked' CHECK (state IN (
      'tracked','claimed','remote_deleted','held','retry_wait','manual_review')),
  hold_reason text,
  operator_hold boolean NOT NULL DEFAULT false,
  legal_hold boolean NOT NULL DEFAULT false,
  claimed_by text,
  lease_until timestamptz,
  deleted_at timestamptz,
  last_error_code text,
  updated_at timestamptz NOT NULL DEFAULT now(),
  CHECK ((output_id IS NOT NULL) <> (source_id IS NOT NULL)),
  CHECK ((storage_kind='drive' AND drive_file_id IS NOT NULL AND local_asset_key IS NULL)
    OR (storage_kind='local' AND drive_file_id IS NULL AND local_asset_key IS NOT NULL)),
  CHECK ((asset_kind='source_video' AND source_id IS NOT NULL)
    OR (asset_kind<>'source_video' AND output_id IS NOT NULL))
);
CREATE UNIQUE INDEX IF NOT EXISTS retention_unique_drive_file
  ON clipflow.retention_assets(drive_file_id) WHERE drive_file_id IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS retention_unique_local_asset
  ON clipflow.retention_assets(local_asset_key) WHERE local_asset_key IS NOT NULL;
CREATE INDEX IF NOT EXISTS retention_due
  ON clipflow.retention_assets(eligible_at, id)
  WHERE state IN ('tracked','retry_wait');

-- Hold forever on unfinished work. Runtime must also check recipient delivery,
-- all platform states, operator holds, rights, and active job dependencies.
-- The claim function deliberately errs on the side of NOT deleting.
CREATE OR REPLACE FUNCTION clipflow.claim_retention_asset(
  p_worker text, p_lease_seconds integer DEFAULT 120)
RETURNS SETOF clipflow.retention_assets
LANGUAGE sql SECURITY INVOKER SET search_path=pg_catalog,clipflow AS $$
  UPDATE clipflow.retention_assets a
     SET state='claimed', claimed_by=p_worker,
         lease_until=now()+make_interval(secs=>least(greatest(p_lease_seconds,30),900)),
         updated_at=now()
    FROM (
      SELECT a0.id FROM clipflow.retention_assets a0
      WHERE a0.state IN ('tracked','retry_wait')
        AND a0.eligible_at <= now()
        AND NOT a0.operator_hold AND NOT a0.legal_hold
        AND (
          (a0.output_id IS NOT NULL AND EXISTS (
            SELECT 1 FROM clipflow.outputs o
              JOIN clipflow.clip_jobs j ON j.id=o.job_id
            WHERE o.id=a0.output_id AND j.state='delivered'
              AND o.telegram_delivery_state='sent'
              AND NOT EXISTS (
                SELECT 1 FROM clipflow.platform_uploads pu
                WHERE pu.output_id=o.id AND pu.state <> 'published_verified'
              )
          )) OR
          (a0.source_id IS NOT NULL AND NOT EXISTS (
            SELECT 1 FROM clipflow.clip_jobs j
            WHERE j.source_id=a0.source_id AND j.state <> 'delivered'
          ) AND NOT EXISTS (
            SELECT 1 FROM clipflow.clip_jobs j
              JOIN clipflow.outputs o ON o.job_id=j.id
            WHERE j.source_id=a0.source_id
              AND (o.telegram_delivery_state <> 'sent' OR EXISTS (
                SELECT 1 FROM clipflow.platform_uploads pu
                WHERE pu.output_id=o.id AND pu.state <> 'published_verified'
              ))
          ))
        )
      ORDER BY a0.eligible_at,a0.id
      FOR UPDATE OF a0 SKIP LOCKED LIMIT 1
    ) candidate
  WHERE a.id=candidate.id
  RETURNING a.*;
$$;
-- Runtime must also block any new job/upload for this asset while claimed.
-- Unknown Drive deletion outcomes are reconciled; NEVER claim remote success
-- on n8n execution success alone. Expired leases are rechecked before claim.
-- Do not rely on the role's broad DELETE privileges; use scoped functions/grants.

CREATE TABLE IF NOT EXISTS clipflow.retention_tombstones (
  asset_id uuid PRIMARY KEY,
  asset_kind text NOT NULL,
  deleted_at timestamptz NOT NULL DEFAULT now(),
  bytes_reported bigint CHECK (bytes_reported IS NULL OR bytes_reported >= 0),
  -- No full Drive URLs, titles, media hashes, or client private details.
  outcome text NOT NULL CHECK (outcome IN ('remote_deleted_verified','metadata_pruned'))
);
CREATE INDEX IF NOT EXISTS retention_tombstones_time
  ON clipflow.retention_tombstones(deleted_at);
COMMIT;

-- DESIGNED RUNTIME TRANSACTION (NOT EXECUTED):
-- 1. Validate claim + hold invariants again (DB) and Drive ownership (API).
-- 2. Delete ONLY the verified file ID in dedicated account via files.delete.
-- 3. Verify file absence; retry uncertain results with same operation ID.
-- 4. Mark retention_assets.remote_deleted, insert sanitized tombstone,
--    THEN prune dependent full metadata with explicit FK-safe ordering.
-- 5. Historical trend_snapshots and topic search request/candidate rows older
--    than 7 days may be pruned in batches, independent of raw media.
-- 6. Keep sanitized audit/tombstones for up to 30 days, then expire.
-- 7. This DDL alone does NOT implement pruning or garbage collection.
