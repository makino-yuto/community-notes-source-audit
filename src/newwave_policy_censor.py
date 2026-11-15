"""Retain previously browser-policy-blocked targets as unknown without fetching."""
import hashlib
import json
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import urlsplit

ROOT=Path(__file__).resolve().parents[1]
R=ROOT/'results'
BLOCKED_HOSTS={'tass.com','britannica.com','unicourt.com','voterrecords.com'}

def main():
    manifest=R/'newwave_semantic_content_manifest_PRIVATE.json'
    d=json.loads(manifest.read_text(encoding='utf-8'))
    selected=[u for u in d['urls'] if any((urlsplit(u['url']).hostname or '')==h or (urlsplit(u['url']).hostname or '').endswith('.'+h) for h in BLOCKED_HOSTS)]
    output=R/'newwave_semantic_content_PRIVATE.jsonl';runlog=R/'newwave_semantic_content_runlog_PRIVATE.jsonl'
    assert not output.exists() and not runlog.exists(), 'Must seed before any content collection.'
    digest=hashlib.sha256(manifest.read_bytes()).hexdigest();now=datetime.now(timezone.utc).isoformat()
    with output.open('x',encoding='utf-8') as h,runlog.open('x',encoding='utf-8') as l:
        for u in selected:
            h.write(json.dumps({'url_sha256':u['url_sha256'],'url':u['url'],'fetch_status':'policy_unassessable','reason':'Prior browser site-safety denial; no content request made in this pass. Not a source failure.','fetched_at_utc':None,'recorded_at_utc':now},ensure_ascii=False)+'\n')
            l.write(json.dumps({'event':'policy_unassessable','utc':now,'manifest_sha256':digest,'url_sha256':u['url_sha256'],'request_made':False})+'\n')
    print('Retained as unassessable without fetching:',len(selected))

if __name__=='__main__':main()
