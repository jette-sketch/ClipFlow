import sys
from pathlib import Path
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'src'))
from upload_recovery import (
    MAX_RETRIES_PER_VIDEO, RETRY_BACKOFF_SECONDS, UploadContractError,
    upload_recovery_decision, all_upload_targets_done, alert_payload,
)
ROOT=Path(__file__).resolve().parents[1]

class UploadRecoveryTests(unittest.TestCase):
    def decision(self, platform='youtube', failure='HTTP_503', n=0, **kwargs):
        return upload_recovery_decision(platform=platform, failure_code=failure,
            video_retry_count=n,drive_draft_verified=True,
            recipient_access_verified=True,**kwargs)
    def test_global_five_retry_budget(self):
        self.assertEqual(MAX_RETRIES_PER_VIDEO,5)
        self.assertEqual(len(RETRY_BACKOFF_SECONDS),5)
        for i in range(5):
            self.assertEqual(self.decision(n=i).action,'retry')
        self.assertEqual(self.decision(platform='tiktok',n=5).action,'alert')
        self.assertEqual(self.decision(n=5).reason,'five_auto_retries_exhausted')
    def test_retries_use_backoff(self):
        for i,expected in enumerate((60,300,900,3600,14400)):
            self.assertEqual(self.decision(n=i).next_retry_in_seconds,expected)
    def test_rate_limit_backoff_honors_larger_retry_after(self):
        self.assertEqual(self.decision(failure='HTTP_429',n=1,retry_after_seconds=1200).next_retry_in_seconds,1200)
        self.assertEqual(self.decision(failure='HTTP_429',n=2,retry_after_seconds=100).next_retry_in_seconds,900)
    def test_terminal_errors_no_retry(self):
        for p,code in [('youtube','COPYRIGHT_BLOCK'), ('youtube','HTTP_401'),
                       ('tiktok','AUTH_REVOKED'), ('tiktok','FILE_FORMAT_CHECK_FAILED')]:
            with self.subTest(p=p,code=code):
                self.assertEqual(self.decision(platform=p,failure=code).action,'alert')
    def test_ambiguous_state_requires_reconciliation_even_budget_remains(self):
        for code in ('TIMEOUT_UNKNOWN','UNKNOWN_ACCEPTANCE',None,'NEW_UNCLASSIFIED_CODE'):
            with self.subTest(code=code):
                self.assertEqual(self.decision(failure=code,n=1).action,'reconcile')
    def test_cannot_upload_without_verified_private_drive(self):
        for a,b in ((False,True),(True,False),(False,False)):
            d=upload_recovery_decision(platform='youtube', failure_code='HTTP_503',
                video_retry_count=0,drive_draft_verified=a,recipient_access_verified=b)
            self.assertEqual(d.action,'alert')
            self.assertEqual(d.reason,'drive_draft_not_verified_do_not_upload')
    def test_success_only_from_verified_acceptance(self):
        d=self.decision(platform='tiktok',failure=None,platform_accepted=True)
        self.assertEqual(d.action,'complete')
        self.assertEqual(d.reason,'platform_acceptance_verified')
        d=upload_recovery_decision(platform='tiktok',failure_code=None,video_retry_count=0,
            drive_draft_verified=False,recipient_access_verified=True,platform_accepted=True)
        self.assertEqual(d.action,'alert')
    def test_invalid_inputs_rejected(self):
        for platform,count in [('instagram',0),('youtube',-1),('youtube',6),('youtube',True)]:
            with self.subTest(platform=platform,count=count),self.assertRaises(UploadContractError):
                self.decision(platform=platform,n=count)
    def test_tiktok_inbox_draft_not_published(self):
        self.assertFalse(all_upload_targets_done({'youtube':'published_verified','tiktok':'tiktok_inbox_draft'}))
        self.assertTrue(all_upload_targets_done({'youtube':'published_verified','tiktok':'published_verified'}))
    def test_each_platform_isolated(self):
        self.assertFalse(all_upload_targets_done({'youtube':'published_verified','tiktok':'retry_wait'}))
        with self.assertRaises(UploadContractError):
            all_upload_targets_done({'youtube':'published_verified'})
    def test_tg_alert_contains_verified_url_for_review(self):
        v='https://drive.google.com/file/d/abcD123456789/view'
        p=alert_payload('a-video-id','tiktok',drive_url=v,failure_code='HTTP_503',retry_count=5)
        self.assertEqual(p['private_drive_url'],v)
        self.assertEqual(p['retry_count'],5)
        self.assertEqual(p['operator_action'],'review_or_resume_after_reconciliation')
        with self.assertRaises(Exception):
            alert_payload('a-video-id','tiktok',drive_url='https://evil.com/x',failure_code='HTTP_503',retry_count=5)
    def test_sql_atomic_reservation_contract_present(self):
        m=(ROOT/'sql/003_clipflow_upload_recovery.sql').read_text()
        for marker in ('FOR UPDATE','retries_reserved BETWEEN 0 AND 5',
                       "RETURN 'duplicate'", "RETURN 'exhausted'",
                       'o.drive_upload_verified AND o.recipient_access_verified',
                       'UNIQUE (output_id, operation_key)','resume_secret_ref'):
            self.assertIn(marker,m)
    def test_two_workflow_invariant(self):
        import json
        flows=list((ROOT/'workflows').glob('*.json'))
        self.assertEqual(len(flows),2)
        self.assertTrue(all(json.loads(f.read_text())['active'] is False for f in flows))

if __name__ == '__main__':unittest.main()
