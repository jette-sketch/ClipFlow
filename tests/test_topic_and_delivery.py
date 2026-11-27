import sys
from pathlib import Path
from datetime import datetime, timezone
import unittest
from unittest.mock import Mock, patch
import importlib.util
import os
import json
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from clipflow_core import (
    parse_command, RejectedCommand, normalize_topic, matches_topic,
    topic_search_parameters, topic_video_candidates, decide_delivery,
    DeliveryHold, private_drive_link_only, MAX_TELEGRAM_VIDEO_BYTES,
)
ROOT=Path(__file__).resolve().parents[1]

class TopicIntentContractTests(unittest.TestCase):
    def test_free_form_example(self):
        actual=parse_command('CF look for trending GTA 6 Videos')
        self.assertEqual(actual.name,'topic_search')
        self.assertEqual(actual.args,('GTA 6','PH'))
        self.assertEqual(normalize_topic(actual.args[0]).canonical_topic,'GTA 6')
    def test_variations_and_slash_find(self):
        for text in ['cf search trending GTA6 videos', 'Cf find popular GTA VI videos',
                     'CF look for recent Grand Theft Auto VI videos','/find GTA 6 videos']:
            with self.subTest(text=text):
                command=parse_command(text)
                self.assertEqual(command.name,'topic_search')
                self.assertEqual(normalize_topic(command.args[0]).scope_key,'gta_6')
    def test_reject_injection_and_unprompted_messages(self):
        for text in ['hey, find GTA6','CF look for trending videos','CF search GTA 6; other',
                     'CF search GTA 6\nanything','CF search /etc/passwd',
                     'CF search ' + 'A'*150]:
            with self.subTest(text=text),self.assertRaises(RejectedCommand):
                parse_command(text)
    def test_gta6_filter_no_gta5(self):
        scope=normalize_topic('GTA 6 videos')
        for title in ['GTA 6 New Trailer', 'Rockstar Grand Theft Auto VI Release Date',
                      'GTA6 gameplay', 'GTA-VI announcement']:
            self.assertTrue(matches_topic(title,scope),title)
        for title in ['GTA 5 Secrets', 'Rockstar GTA V News', 'Fortnite and the next GTA',
                      'Top 10 Gaming Videos', 'GTA 6 mentioned only in description']:
            if title.startswith('GTA 6 mentioned'):
                continue
            self.assertFalse(matches_topic(title,scope),title)
    def test_modifier_must_match(self):
        scope=normalize_topic('GTA 6 trailer videos')
        self.assertTrue(matches_topic('GTA 6 Trailer 2 analysis',scope))
        self.assertFalse(matches_topic('GTA 6 Gameplay',scope))
        self.assertFalse(matches_topic('GTA V Trailer',scope))
    def test_general_topic_all_tokens(self):
        spec=normalize_topic('AI automation videos')
        self.assertTrue(matches_topic('AI Automation Workflow for Teams',spec))
        self.assertFalse(matches_topic('AI Generated Landscape Art',spec))
    def test_search_payload_scoped(self):
        spec=normalize_topic('GTA 6 videos')
        params=topic_search_parameters(spec,'2026-11-20T00:00:00Z',region='PH')
        self.assertIn('GTA 6',params['q'])
        self.assertEqual(params['type'],'video')
        self.assertEqual(params['publishedAfter'],'2026-11-20T00:00:00Z')
        self.assertNotIn('category',params)
    def test_filter_candidates_and_label_proxy(self):
        spec=normalize_topic('GTA 6 Videos')
        search={'items':[{'id':{'videoId':'aaaaaaaaaaa'}},
                         {'id':{'videoId':'bbbbbbbbbbb'}},
                         {'id':{'videoId':'ccccccccccc'}}]}
        details={'items':[
            {'id':'aaaaaaaaaaa','snippet':{'title':'GTA 6 official news','publishedAt':'2026-11-26T00:00:00Z'},'statistics':{'viewCount':'10000'}},
            {'id':'bbbbbbbbbbb','snippet':{'title':'GTA 5 tips','publishedAt':'2026-11-26T00:00:00Z'},'statistics':{'viewCount':'999999999'}},
            {'id':'ccccccccccc','snippet':{'title':'Grand Theft Auto VI details','publishedAt':'2026-11-25T00:00:00Z'},'statistics':{'viewCount':'1200'}}
        ]}
        result=topic_video_candidates(search,details,spec,datetime(2026,11,27,tzinfo=timezone.utc))
        self.assertEqual([r['video_id'] for r in result],['aaaaaaaaaaa','ccccccccccc'])
        self.assertTrue(all('not_verified_velocity' in r['signal'] for r in result))
    def test_empty_topic_results_never_expand(self):
        spec=normalize_topic('GTA 6')
        res=topic_video_candidates({'items':[{'id':{'videoId':'bbbbbbbbbbb'}}]},
            {'items':[{'id':'bbbbbbbbbbb','snippet':{'title':'GTA 5'}}]},spec,
            datetime(2026,11,27,tzinfo=timezone.utc))
        self.assertEqual(res,[])

class TelegramDeliveryContractTests(unittest.TestCase):
    def mode(self,size,**kwargs):
        return decide_delivery(size,drive_uploaded_and_verified=True,
                               recipient_drive_access_verified=True,**kwargs)
    def test_50_mb_boundary_in_decimal_bytes(self):
        self.assertEqual(MAX_TELEGRAM_VIDEO_BYTES,50_000_000)
        self.assertEqual(self.mode(49_999_999).mode,'telegram_video')
        self.assertEqual(self.mode(50_000_000).mode,'telegram_video')
        self.assertEqual(self.mode(50_000_001).mode,'drive_link_only')
        self.assertEqual(self.mode(100_000_000).mode,'drive_link_only')
    def test_explicit_telegram_file_limit_rejection_falls_back(self):
        self.assertEqual(self.mode(15_000_000,telegram_error='HTTP_413').mode,
                         'drive_link_only')
        self.assertEqual(self.mode(15_000_000,telegram_error='FILE_TOO_BIG').mode,
                         'drive_link_only')
    def test_unknown_error_halts_to_avoid_duplicate(self):
        with self.assertRaises(DeliveryHold):
            self.mode(10_000_000,telegram_error='TIMEOUT_UNKNOWN')
    def test_cannot_link_unverified_drive_or_recipient(self):
        for uploaded,access in [(False,True),(True,False),(False,False)]:
            with self.subTest(uploaded=uploaded,access=access),self.assertRaises(DeliveryHold):
                decide_delivery(100_000_000,drive_uploaded_and_verified=uploaded,
                                recipient_drive_access_verified=access)
    def test_unknown_size_halts(self):
        for size in (None,0,-1,True,'100MB'):
            with self.subTest(size=size),self.assertRaises(DeliveryHold):
                self.mode(size)
    def test_link_only_body_contains_only_url(self):
        decision=self.mode(50_000_001)
        url='https://drive.google.com/file/d/1xyzDEFGHIJK/view'
        self.assertEqual(private_drive_link_only(url,decision),url)
        with self.assertRaises(DeliveryHold):
            private_drive_link_only('https://evil.example/url',decision)
        with self.assertRaises(DeliveryHold):
            private_drive_link_only(url,self.mode(1_000_000))
    def test_poller_supports_cf_text(self):
        p=(ROOT/'src/telegram_poller_reference.py').read_text()
        self.assertIn("re.match(r'^\\s*CF\\b'",p)
    def test_poller_actually_forwards_cf_message_for_allowed_actor(self):
        module_path=ROOT/'src/telegram_poller_reference.py'
        spec=importlib.util.spec_from_file_location('cf_poller_test',module_path)
        module=importlib.util.module_from_spec(spec)
        with patch.dict(os.environ, {
                'CLIPFLOW_TELEGRAM_BOT_TOKEN':'fake-TEST-token',
                'CLIPFLOW_ALLOWED_CHAT_ID':'900',
                'CLIPFLOW_ALLOWED_USER_ID':'800',
                'CLIPFLOW_HMAC_KEY':'test-secret'}):
            spec.loader.exec_module(module)
        response=Mock()
        response.json.return_value={'accepted':True}
        client=Mock()
        client.post.return_value=response
        good={'update_id':42,'message':{'chat':{'id':900},'from':{'id':800},
                                      'text':'CF look for trending GTA 6 Videos'}}
        module.forward(client,good)
        client.post.assert_called_once()
        sent=client.post.call_args.kwargs['json']
        self.assertEqual(sent['text'],good['message']['text'])
        self.assertEqual(sent['sender_id'],800)
        self.assertTrue(sent['signature'])
        wrong={'update_id':43,'message':{'chat':{'id':900},'from':{'id':801},
                                       'text':'CF look for trending GTA 6 Videos'}}
        module.forward(client,wrong)
        client.post.assert_called_once()
    def test_poller_discards_ambient_chat(self):
        module_path=ROOT/'src/telegram_poller_reference.py'
        spec=importlib.util.spec_from_file_location('cf_poller_test2',module_path)
        module=importlib.util.module_from_spec(spec)
        with patch.dict(os.environ, {
                'CLIPFLOW_TELEGRAM_BOT_TOKEN':'fake-TEST-token',
                'CLIPFLOW_ALLOWED_CHAT_ID':'900',
                'CLIPFLOW_ALLOWED_USER_ID':'800',
                'CLIPFLOW_HMAC_KEY':'test-secret'}):
            spec.loader.exec_module(module)
        client=Mock()
        module.forward(client,{'update_id':44,'message':{'chat':{'id':900},'from':{'id':800},
                                                       'text':'I am playing GTA6'}})
        client.post.assert_not_called()
    def test_migration_is_unapplied_and_scoped(self):
        s=(ROOT/'sql/002_clipflow_topic_and_delivery.sql').read_text()
        self.assertIn('UNAPPLIED DRAFT',s)
        self.assertIn('clipflow.topic_search_requests',s)
        self.assertIn('drive_upload_verified',s)
        self.assertIn('recipient_access_verified',s)

if __name__=='__main__':unittest.main()
