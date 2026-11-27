import sys
from pathlib import Path
import json
import unittest
from datetime import datetime, timedelta, timezone
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from retention_policy import (RETENTION_DAYS, RETENTION_SECONDS, RETENTION_SCHEDULE_PHT,
    retention_decision, drive_delete_preflight, remote_delete_receipt,RetentionSafetyError)
ROOT=Path(__file__).resolve().parents[1]
NOW=datetime(2026,11,27,0,0,tzinfo=timezone.utc)

class RetentionContracts(unittest.TestCase):
    def decide(self, days=8, **kwargs):
        data=dict(created_at=NOW-timedelta(days=days),now=NOW,kind='rendered_clip',
            telegram_delivery_state='sent',job_state='delivered',platform_states={})
        data.update(kwargs)
        return retention_decision(**data)
    def test_duration_exactly_168_hours(self):
        self.assertEqual(RETENTION_DAYS,7)
        self.assertEqual(RETENTION_SECONDS,604800)
        self.assertEqual(RETENTION_SCHEDULE_PHT,'03:15')
    def test_seven_days_exact_boundary(self):
        self.assertEqual(self.decide(days=7).action,'delete_eligible')
        self.assertEqual(self.decide(days=6).action,'wait')
        self.assertEqual(self.decide(created_at=NOW-timedelta(seconds=604799)).action,'wait')
    def test_active_processing_holds(self):
        for state in ('queued','processing','retry','rendered','drive_uploaded'):
            with self.subTest(state=state): self.assertEqual(self.decide(job_state=state).action,'hold')
    def test_unknown_job_state_fails_closed(self):
        self.assertEqual(self.decide(job_state='mystery').action,'hold')
        self.assertEqual(self.decide(job_state=None).action,'hold')
    def test_failed_or_blocked_job_preserved(self):
        for state in ('failed','blocked'):
            self.assertEqual(self.decide(job_state=state).action,'hold')
    def test_unresolved_platforms_hold(self):
        for state in ('retry_wait','retry_exhausted','reconcile_required','failed_terminal',
                      'integration_blocked','tiktok_inbox_draft','youtube_private_uploaded','uploading'):
            with self.subTest(state=state):
                self.assertEqual(self.decide(platform_states={'tiktok':state}).action,'hold')
    def test_verified_publishing_does_not_block_retention(self):
        self.assertEqual(self.decide(platform_states={'youtube':'published_verified','tiktok':'published_verified'}).action,'delete_eligible')
    def test_unknown_or_missing_platform_inventory_holds(self):
        self.assertEqual(self.decide(platform_states=None).action,'hold')
        self.assertEqual(self.decide(platform_states={'facebook':'published_verified'}).action,'hold')
    def test_telegram_delivery_missing_holds(self):
        for state in ('pending','sending','unknown','failed',None):
            self.assertEqual(self.decide(telegram_delivery_state=state).action,'hold')
    def test_explicit_and_legal_holds(self):
        self.assertEqual(self.decide(operator_hold=True).action,'hold')
        self.assertEqual(self.decide(legal_hold=True).action,'hold')
        self.assertEqual(self.decide(unresolved_incident=True).action,'hold')
        self.assertEqual(self.decide(pending_dependents=True).action,'hold')
    def test_source_video_age_cleanup_after_terminal_dependents(self):
        self.assertEqual(self.decide(kind='source_video',telegram_delivery_state=None).action,'delete_eligible')
        self.assertEqual(self.decide(kind='source_video',pending_dependents=True).action,'hold')
    def test_naive_timestamps_and_clock_skew_fail_closed(self):
        with self.assertRaises(RetentionSafetyError):self.decide(created_at=datetime(2026,11,18))
        with self.assertRaises(RetentionSafetyError):self.decide(now=datetime(2026,11,28))
        self.assertEqual(self.decide(created_at=NOW+timedelta(minutes=1)).action,'hold')
    def metadata(self):
        return {'id':'driveFileABC123','mimeType':'video/mp4','parents':['folder-clipflow-drafts'],
            'ownedByMe':True,'owners':[{'emailAddress':'clipflow@example.com'}],
            'capabilities':{'canDelete':True},'appProperties':{'clipflow_project':'clipflow-only-42'},
            'trashed':False}
    def preflight(self, meta=None, **kwargs):
        drive_delete_preflight(expected_file_id='driveFileABC123',
           drive_metadata=meta if meta is not None else self.metadata(),
           project_marker=kwargs.get('project_marker','clipflow-only-42'),
           permitted_parent_ids=kwargs.get('permitted_parent_ids',{'folder-clipflow-drafts'}),
           expected_drive_owner=kwargs.get('expected_drive_owner','clipflow@example.com'))
    def test_drive_preflight_verified_identity_passes(self):
        self.preflight()
    def test_drive_delete_wrong_file_rejected(self):
        m=self.metadata();m['id']='other';
        with self.assertRaises(RetentionSafetyError):self.preflight(m)
    def test_no_folder_recursion(self):
        m=self.metadata();m['mimeType']='application/vnd.google-apps.folder'
        with self.assertRaises(RetentionSafetyError):self.preflight(m)
    def test_wrong_drive_owner_rejected(self):
        m=self.metadata();m['owners']=[{'emailAddress':'other@example.com'}]
        with self.assertRaises(RetentionSafetyError):self.preflight(m)
        m=self.metadata();m['ownedByMe']=False
        with self.assertRaises(RetentionSafetyError):self.preflight(m)
    def test_wrong_folder_or_shared_drive_rejected(self):
        m=self.metadata();m['parents']=['personal-folder']
        with self.assertRaises(RetentionSafetyError):self.preflight(m)
        m=self.metadata();m['driveId']='sharedDrive-id'
        with self.assertRaises(RetentionSafetyError):self.preflight(m)
    def test_not_authorized_to_delete_rejected(self):
        m=self.metadata();m['capabilities']={'canDelete':False}
        with self.assertRaises(RetentionSafetyError):self.preflight(m)
        m=self.metadata();m['trashed']=True
        with self.assertRaises(RetentionSafetyError):self.preflight(m)
    def test_project_marker_required(self):
        m=self.metadata();m['appProperties']={}
        with self.assertRaises(RetentionSafetyError):self.preflight(m)
    def test_no_allowlist_fails_closed(self):
        with self.assertRaises(RetentionSafetyError):self.preflight(permitted_parent_ids=set())
    def test_delete_receipt_cannot_fake_confirmation(self):
        self.assertEqual(remote_delete_receipt(http_status=204,verified_absent=False),'reconcile_required')
        self.assertEqual(remote_delete_receipt(http_status=404,verified_absent=True),'remote_deleted_verified')
        self.assertEqual(remote_delete_receipt(http_status=403,verified_absent=True),'retry_or_alert')
    def test_two_workflows_with_daily_retention_branch(self):
        paths=list((ROOT/'workflows').glob('*.json'))
        self.assertEqual(len(paths),2)
        flows={p.name:json.loads(p.read_text()) for p in paths}
        self.assertTrue(all(flow['active'] is False for flow in flows.values()))
        flow=flows['02_autonomous_clip_producer.json']
        self.assertEqual(len(flow['nodes']),4)
        self.assertEqual(flow['settings']['timezone'],'Asia/Manila')
        self.assertIn('Retention Daily 03:15 PHT',flow['connections'])
        node=next(x for x in flow['nodes'] if x['id']=='clipflow-02-retention-dispatch')
        self.assertIn('/v1/retention/sweep',node['parameters']['url'])
        self.assertEqual(node['parameters']['genericAuthType'],'httpHeaderAuth')
    def test_sql_migration_has_scope_and_bounded_claim(self):
        text=(ROOT/'sql/004_clipflow_seven_day_retention.sql').read_text()
        for phrase in ('UNAPPLIED DRAFT','operator_hold','legal_hold','FOR UPDATE OF a0 SKIP LOCKED LIMIT 1',
                       "interval '7 days'",'clipflow.retention_tombstones',"state='claimed'",'NOT EXISTS'):
            self.assertIn(phrase,text)
if __name__=='__main__':unittest.main()
