"""Assemble all 200 fixed-claim notes with uniform collected source text."""
import hashlib
import json
from pathlib import Path
from urllib.parse import urldefrag

ROOT=Path(__file__).resolve().parents[1]
R=ROOT/'results'

def readl(p):return [json.loads(s) for s in p.read_text(encoding='utf-8').splitlines()]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    key=json.loads((R/'newwave_semantic_key_PRIVATE.json').read_text(encoding='utf-8'))
    candidates={p['post_id']:p for p in readl(R/'revision_samepost_candidates_v2_PRIVATE.jsonl')}
    alignment={p['code']:p for p in readl(R/'newwave_alignment_trials_PRIVATE.jsonl')}
    assert len(alignment)==100 and all(p['valid'] for p in alignment.values())
    contentpath=R/'newwave_semantic_content_PRIVATE.jsonl'
    content={p['url_sha256']:p for p in readl(contentpath)}
    assert len(content)==319
    out=[]
    for p in key:
        candidate=candidates[p['post_id']]
        for side in ('A','B'):
            note=candidate['ai' if p['groups'][side]=='AI_API' else 'non_api']
            assert note['note_id']==p['sides'][side]
            urls={}
            for u in note['external_urls']:
                network=urldefrag(u['normalized_url']).url
                urls.setdefault(network,[]).append(u['normalized_url'])
            sources=[]
            for i,(url,variants) in enumerate(urls.items(),1):
                d=content[hashlib.sha256(url.encode()).hexdigest()]
                parsed=d.get('parsed') or {};maintext=parsed.get('main_text') or {}
                text=maintext.get('text','')
                sources.append({'source_id':f'S{i}','citation_urls':variants,
                    'final_url':d.get('final_url'),'status_code':d.get('status_code'),
                    'fetch_status':d.get('fetch_status'),'fetched_utc':d.get('fetched_at_utc'),
                    'format':parsed.get('format'),'title':parsed.get('title',''),
                    'main_selector':parsed.get('main_selector'),'main_text':text[:24000],
                    'coverage':{'input_chars':min(24000,len(text)),'extracted_chars_total':maintext.get('chars_total',0),
                                'input_truncated':len(text)>24000 or maintext.get('truncated',False),
                                'body_capped_2mb':d.get('body_capped_2mb',False),
                                'pdf_pages_extracted':parsed.get('pages_extracted'),
                                'pdf_page_count':parsed.get('page_count')},
                    'body_sha256':d.get('body_sha256'),'main_text_saved_sha256':maintext.get('sha256_saved')})
            response=alignment[p['code']]['response']
            out.append({'code':p['code']+side,'note_text':note['summary'],
                'fixed_main_claim':response['main_claim_a' if side=='A' else 'main_claim_b'],
                'other_material_claims_not_scored':response['other_material_claims_a' if side=='A' else 'other_material_claims_b'],
                'original_post_or_media_available':False,'sources':sources})
    target=R/'newwave_support_packet_blind.json';assert not target.exists()
    target.write_text(json.dumps(out,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    manifest={'notes':len(out),'pairs':len(key),'content_urls':len(content),'source_slots':sum(len(x['sources']) for x in out),
        'packet_sha256':sha(target),'inputs_sha256':{p.name:sha(p) for p in [R/'newwave_semantic_key_PRIVATE.json',R/'revision_samepost_candidates_v2_PRIVATE.jsonl',R/'newwave_alignment_trials_PRIVATE.jsonl',contentpath,Path(__file__)]}}
    (R/'newwave_support_packet_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(manifest,indent=2))

if __name__=='__main__':main()
