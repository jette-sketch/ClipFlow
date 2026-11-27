"""Reference outbound Telegram long-polling bridge.

NOT DEPLOYMENT READY: requires a hardened command API, secret handling, tested
restart behavior and a dedicated bot. HMAC covers actor identity and message.
"""
from __future__ import annotations
import json
import os
import re
from pathlib import Path
import time
from clipflow_core import signed_update

BOT_TOKEN=os.environ['CLIPFLOW_TELEGRAM_BOT_TOKEN']
CHAT_ID=int(os.environ['CLIPFLOW_ALLOWED_CHAT_ID'])
SENDER_ID=int(os.environ['CLIPFLOW_ALLOWED_USER_ID'])
SHARED_KEY=os.environ['CLIPFLOW_HMAC_KEY']
TARGET=os.getenv('CLIPFLOW_N8N_WEBHOOK','http://n8n:5678/webhook/clipflow-command')
OFFSET_FILE=Path('/state/telegram-offset.json')

def get_offset():
    try:
        return max(0,int(json.loads(OFFSET_FILE.read_text())['offset']))
    except (OSError,TypeError,KeyError,ValueError):
        return 0

def save_offset(offset):
    OFFSET_FILE.parent.mkdir(parents=True,exist_ok=True)
    tmp=OFFSET_FILE.with_suffix('.tmp')
    tmp.write_text(json.dumps({'offset':offset}))
    tmp.replace(OFFSET_FILE)

def forward(session, update):
    msg=update.get('message') or {}
    chat=int((msg.get('chat') or {}).get('id',0))
    sender=int((msg.get('from') or {}).get('id',0))
    raw=msg.get('text','')
    # Drop unauthorized/non-command updates but advance offset.
    if (chat!=CHAT_ID or sender!=SENDER_ID or not isinstance(raw,str)
        or not (raw.startswith('/') or re.match(r'^\s*CF\b',raw,re.IGNORECASE))):
        return
    uid=int(update['update_id'])
    data={'update_id':uid,'chat_id':chat,'sender_id':sender,'text':raw,
          'signature':signed_update(SHARED_KEY,uid,chat,sender,raw)}
    response=session.post(TARGET,json=data,timeout=55)
    response.raise_for_status()
    if response.json().get('accepted') is not True:
        raise RuntimeError('Command was not durably accepted by gateway; retry')

def run():
    import requests  # optional production dependency; requirements-poller.txt
    offset=get_offset()
    session=requests.Session()
    while True:
        try:
            response=session.get('https://api.telegram.org/bot'+BOT_TOKEN+'/getUpdates',
                params={'offset':offset,'limit':20,'timeout':25,
                        'allowed_updates':json.dumps(['message'])},timeout=35)
            response.raise_for_status()
            payload=response.json()
            if payload.get('ok') is not True:
                raise RuntimeError('Telegram API failure')
            for update in payload['result']:
                forward(session,update)
                offset=int(update['update_id'])+1
                save_offset(offset)
        except Exception as exc:
            # No token or message content in logs.
            print('poller_retry:',type(exc).__name__,flush=True)
            time.sleep(10)

if __name__=='__main__':run()
