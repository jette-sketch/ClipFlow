import json
from pathlib import Path
import unittest
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from clipflow_core import (parse_command,RejectedCommand,signed_update,authorize_update,
    chart_rows, trend_velocity,validate_clip_window)
ROOT=Path(__file__).resolve().parents[1]
class PureContractTests(unittest.TestCase):
    def test_default_trending(self):
        self.assertEqual(parse_command('/trending').args,('PH','all'))
        self.assertEqual(parse_command('/trending US gaming').args,('US','gaming'))
    def test_commands(self):
        self.assertEqual(parse_command('/source lecture.mp4 owned').name,'source')
        self.assertEqual(parse_command('/clip 12345678-1234-1234-1234-123456789abc').args[0],
                         '12345678-1234-1234-1234-123456789abc')
    def test_reject_traversal_and_injection(self):
        for command in ('/source ../../passwd.mp4 owned','/source file.mp4 unlicensed',
                        '/clip ../../../tmp','/trending RU gaming','/trending PH arbitrary',
                        '/help trailing','/source foo bar owned'):
            with self.subTest(command=command),self.assertRaises(RejectedCommand):
                parse_command(command)
    def test_hmac_chat_and_sender(self):
        p={'update_id':12,'chat_id':900,'sender_id':800,'text':'/status'}
        p['signature']=signed_update('test-secret',12,900,800,'/status')
        self.assertTrue(authorize_update('test-secret',900,800,p))
        self.assertFalse(authorize_update('test-secret',900,801,p))
        self.assertFalse(authorize_update('test-secret',901,800,p))
        p['text']='/clip other'
        self.assertFalse(authorize_update('test-secret',900,800,p))
    def test_chart_is_not_viral_rank(self):
        p={'items':[{'id':'qwerty12345','snippet':{'title':'Example','channelTitle':'Source'},'statistics':{'viewCount':'120'}}]}
        r=chart_rows(p,'PH','gaming')
        self.assertEqual(r[0]['views'],120)
        self.assertEqual(r[0]['signal'],'regional_popularity_chart_not_verified_viral')
    def test_velocity_requires_two_snapshots(self):
        self.assertEqual(trend_velocity(200,100,2),50)
        self.assertIsNone(trend_velocity(200,100,.5))
        self.assertIsNone(trend_velocity(100,200,2))
    def test_window(self):
        validate_clip_window(10,30,100)
        for args in ((-1,40,100),(10,1000,100),(10,12,100),(10,80,100)):
            with self.assertRaises(ValueError):validate_clip_window(*args)
class WorkflowContractTests(unittest.TestCase):
    def test_two_distinct_importable_workflow_shapes(self):
        paths=sorted((ROOT/'workflows').glob('*.json'))
        self.assertEqual(len(paths),2)
        seen=[]
        for path in paths:
            flow=json.loads(path.read_text())
            self.assertFalse(flow['active'])
            self.assertTrue(flow['nodes'])
            self.assertTrue(flow['connections'])
            self.assertTrue(all(n.get('type','').startswith('n8n-nodes-base.') for n in flow['nodes']))
            self.assertFalse(any('api.telegram.org/bot' in str(n) for n in flow['nodes']))
            seen.append({n['type'] for n in flow['nodes']})
        self.assertIn('n8n-nodes-base.webhook',seen[0]); self.assertIn('n8n-nodes-base.scheduleTrigger',seen[1])
if __name__=='__main__':unittest.main()
