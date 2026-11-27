"""ClipFlow P0 v0.5: PURE retention decision and delete-preflight contracts.

No cloud calls and no destructive actions. Runtime must execute a durable
Neon claim, recheck just before remote deletion, and confirm remote absence
before deleting its metadata.  No source files in other projects are in scope.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Literal

RETENTION_DAYS = 7
RETENTION_SECONDS = RETENTION_DAYS * 24 * 60 * 60
RETENTION_SCHEDULE_PHT = '03:15'
TERMINAL_JOB_STATES = frozenset({'delivered', 'failed', 'blocked'})
HOLD_JOB_STATES = frozenset({'queued', 'processing', 'retry', 'rendered', 'drive_uploaded'})
UNRESOLVED_PLATFORM_STATES = frozenset({
    'draft_archived', 'queued', 'uploading', 'retry_wait', 'reconcile_required',
    'youtube_private_uploaded', 'tiktok_inbox_draft', 'failed_terminal',
    'retry_exhausted', 'integration_blocked'
})

@dataclass(frozen=True)
class RetentionDecision:
    action: Literal['delete_eligible', 'hold', 'wait']
    reason: str

class RetentionSafetyError(ValueError):
    pass


def _check_datetime(value: datetime, name: str) -> None:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise RetentionSafetyError(f'{name} must be timezone-aware')


def retention_decision(
    *, created_at: datetime, now: datetime, kind: str, telegram_delivery_state: str | None,
    job_state: str | None, platform_states: dict[str, str] | None,
    pending_dependents: bool = False, unresolved_incident: bool = False,
    legal_hold: bool = False, operator_hold: bool = False,
) -> RetentionDecision:
    """Decide eligibility. No time-based deletion overrides an active hold.

    kind: 'rendered_clip' or 'source_video'. Other file artifacts associated
    with outputs use the same rendered_clip safety rule.
    """
    _check_datetime(created_at, 'created_at')
    _check_datetime(now, 'now')
    if kind not in ('rendered_clip', 'source_video'):
        raise RetentionSafetyError('unsupported retention kind')
    if legal_hold or operator_hold:
        return RetentionDecision('hold', 'explicit_retention_hold')
    if unresolved_incident:
        return RetentionDecision('hold', 'unresolved_recovery_incident')
    if pending_dependents:
        return RetentionDecision('hold', 'dependent_job_or_asset_active')
    if job_state is None or job_state not in TERMINAL_JOB_STATES | HOLD_JOB_STATES:
        return RetentionDecision('hold', 'unknown_job_state')
    if job_state in HOLD_JOB_STATES:
        return RetentionDecision('hold', 'active_or_incomplete_job')
    if job_state in ('failed', 'blocked'):
        return RetentionDecision('hold', 'failed_or_blocked_job_requires_resolution')
    if kind == 'rendered_clip' and telegram_delivery_state != 'sent':
        return RetentionDecision('hold', 'recipient_delivery_not_verified')
    if platform_states is None:
        return RetentionDecision('hold', 'platform_state_inventory_unverified')
    if any(p not in ('youtube', 'tiktok') for p in platform_states):
        return RetentionDecision('hold', 'unknown_platform_target')
    if any(state != 'published_verified' for state in platform_states.values()):
        return RetentionDecision('hold', 'destination_not_resolved')
    if now < created_at:
        return RetentionDecision('hold', 'clock_skew')
    if now - created_at < timedelta(seconds=RETENTION_SECONDS):
        return RetentionDecision('wait', 'less_than_seven_full_days')
    return RetentionDecision('delete_eligible', 'seven_days_elapsed_and_no_holds')


def drive_delete_preflight(
    *, expected_file_id: str, drive_metadata: dict, project_marker: str,
    permitted_parent_ids: set[str], expected_drive_owner: str,
) -> None:
    """Raises unless file belongs to THIS project and can be deleted.

    Requires Drive files.get(fields='id,mimeType,parents,ownedByMe,owners(emailAddress),
    capabilities(canDelete),appProperties,trashed,driveId'). Never delete folders.
    """
    if not expected_file_id or not isinstance(drive_metadata, dict):
        raise RetentionSafetyError('missing recorded file ID or provider metadata')
    if drive_metadata.get('id') != expected_file_id:
        raise RetentionSafetyError('file ID changed or mismatch')
    if drive_metadata.get('mimeType') == 'application/vnd.google-apps.folder':
        raise RetentionSafetyError('folder recursive delete prohibited')
    if drive_metadata.get('driveId'):
        raise RetentionSafetyError('shared drive deletion not supported')
    if drive_metadata.get('ownedByMe') is not True:
        raise RetentionSafetyError('Drive credential is not the file owner')
    if drive_metadata.get('capabilities', {}).get('canDelete') is not True:
        raise RetentionSafetyError('provider cannot delete file')
    if drive_metadata.get('trashed') is True:
        raise RetentionSafetyError('pre-trashed file requires separate reconciliation')
    if not isinstance(permitted_parent_ids, set) or not permitted_parent_ids:
        raise RetentionSafetyError('project root allowlist not configured')
    parents = drive_metadata.get('parents', [])
    if len(parents) != 1 or parents[0] not in permitted_parent_ids:
        raise RetentionSafetyError('file is not directly within authorized media folders')
    if not project_marker or drive_metadata.get('appProperties', {}).get('clipflow_project') != project_marker:
        raise RetentionSafetyError('file lacks correct project ownership marker')
    owners = drive_metadata.get('owners', [])
    if not expected_drive_owner or not any(
        isinstance(owner, dict) and owner.get('emailAddress', '').lower() == expected_drive_owner.lower()
        for owner in owners
    ):
        raise RetentionSafetyError('dedicated Gmail identity mismatch')


def remote_delete_receipt(*, http_status: int, verified_absent: bool) -> str:
    """Only a confirmed post-delete absence is strong enough for metadata prune.

    DELETE 204 alone is insufficient if a proxy or API error masked the outcome.
    404 without earlier successful ownership proof is not an authorization proof.
    """
    if http_status not in (204, 404):
        return 'retry_or_alert'
    return 'remote_deleted_verified' if verified_absent else 'reconcile_required'
