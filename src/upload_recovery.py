"""Pure upload-recovery contracts for ClipFlow.

P0 contract only; no real platform transport, Neon connection, or OAuth.
A finished video/clip has ONE shared automated retry budget across platforms.
A retry is *reserved atomically in Neon* before execution. Initial upload attempts
are not retries. This file classifies outcomes, not permission to publish.
"""
from dataclasses import dataclass
from typing import Literal

MAX_RETRIES_PER_VIDEO = 5
RETRY_BACKOFF_SECONDS = (60, 300, 900, 3600, 14400)
PLATFORMS = frozenset(("youtube", "tiktok"))
TRANSIENT = frozenset((
    "HTTP_408", "HTTP_429", "HTTP_500", "HTTP_502", "HTTP_503", "HTTP_504",
    "CONNECTION_RESET", "SERVER_UNAVAILABLE", "RATE_LIMIT_TEMPORARY",
))
TERMINAL = frozenset((
    "HTTP_400", "HTTP_401", "HTTP_403", "COPYRIGHT_BLOCK",
    "INVALID_MEDIA", "AUTH_REVOKED", "SCOPE_NOT_AUTHORIZED",
    "POLICY_REJECTED", "FILE_FORMAT_CHECK_FAILED", "ACCOUNT_BANNED",
))
AMBIGUOUS = frozenset(("TIMEOUT_UNKNOWN", "CONNECTION_LOST_AFTER_REQUEST", "UNKNOWN_ACCEPTANCE"))


@dataclass(frozen=True)
class UploadDecision:
    action: Literal["retry", "reconcile", "alert", "complete"]
    reason: str
    next_retry_in_seconds: int | None = None
    draft_location: Literal["verified_private_drive", "unverified"] = "unverified"


class UploadContractError(ValueError):
    pass


def upload_recovery_decision(*, platform: str, failure_code: str | None,
                             video_retry_count: int, drive_draft_verified: bool,
                             recipient_access_verified: bool,
                             platform_accepted: bool = False,
                             retry_after_seconds: int | None = None) -> UploadDecision:
    """Classify the *observed* upload result; never infer acceptance from a timeout.

    video_retry_count is the number of retry reservations for one finished video,
    aggregated across YouTube and TikTok, not the render-job attempt count.
    A returned 'retry' is a proposal; runtime MUST atomically reserve the slot.
    """
    if platform not in PLATFORMS:
        raise UploadContractError('Unsupported upload platform')
    if type(video_retry_count) is not int or not 0 <= video_retry_count <= MAX_RETRIES_PER_VIDEO:
        raise UploadContractError('Invalid retry counter')
    if type(drive_draft_verified) is not bool or type(recipient_access_verified) is not bool:
        raise UploadContractError('Invalid Drive verification flags')
    if type(platform_accepted) is not bool:
        raise UploadContractError('Invalid platform acceptance flag')
    if retry_after_seconds is not None and (type(retry_after_seconds) is not int
                                             or not 0 <= retry_after_seconds <= 86400):
        raise UploadContractError('Invalid server retry delay')
    if not drive_draft_verified or not recipient_access_verified:
        return UploadDecision('alert', 'drive_draft_not_verified_do_not_upload')
    if platform_accepted:
        return UploadDecision('complete', 'platform_acceptance_verified',
                              draft_location='verified_private_drive')
    if not failure_code or not isinstance(failure_code, str):
        return UploadDecision('reconcile', 'unknown_upload_status_must_reconcile',
                              draft_location='verified_private_drive')
    code = failure_code.upper()
    if code in AMBIGUOUS:
        return UploadDecision('reconcile', 'unknown_upload_status_must_reconcile',
                              draft_location='verified_private_drive')
    if code in TERMINAL:
        return UploadDecision('alert', 'terminal_error_no_automatic_retry',
                              draft_location='verified_private_drive')
    if code not in TRANSIENT:
        return UploadDecision('reconcile', 'unrecognized_error_requires_investigation',
                              draft_location='verified_private_drive')
    if video_retry_count >= MAX_RETRIES_PER_VIDEO:
        return UploadDecision('alert', 'five_auto_retries_exhausted',
                              draft_location='verified_private_drive')
    delay = RETRY_BACKOFF_SECONDS[video_retry_count]
    if retry_after_seconds is not None:
        delay = max(delay, retry_after_seconds)
    return UploadDecision('retry', 'verified_transient_failure', delay,
                          draft_location='verified_private_drive')


def all_upload_targets_done(platform_states: dict[str, str]) -> bool:
    """Do not mark the entire clip published unless *both* are verified.

    For TikTok inbox drafts, 'draft_delivered' is NOT a published state.
    """
    if set(platform_states) != PLATFORMS:
        raise UploadContractError('Both platform states must be supplied')
    return all(v == 'published_verified' for v in platform_states.values())


def alert_payload(video_id: str, platform: str, *, drive_url: str,
                  failure_code: str, retry_count: int) -> dict:
    """Payload for Telegram alert outbox. Runtime must authorize recipient.

    Returning a URL here does not make the underlying Drive file public.
    """
    if not video_id or not isinstance(video_id, str) or len(video_id) > 128:
        raise UploadContractError('Invalid video identity')
    if platform not in PLATFORMS:
        raise UploadContractError('Unsupported platform')
    if type(retry_count) is not int or not 0 <= retry_count <= MAX_RETRIES_PER_VIDEO:
        raise UploadContractError('Invalid retry count')
    from clipflow_core import private_drive_link_only, DeliveryDecision
    valid_url = private_drive_link_only(drive_url, DeliveryDecision('drive_link_only', 'alert'))
    if not isinstance(failure_code, str) or len(failure_code) > 120:
        raise UploadContractError('Invalid error code')
    return {'kind':'upload_recovery_alert', 'video_id':video_id,
            'platform':platform, 'retry_count':retry_count,
            'reason':failure_code, 'private_drive_url':valid_url,
            'operator_action':'review_or_resume_after_reconciliation'}
