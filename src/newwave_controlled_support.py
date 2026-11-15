"""Synthetic known-answer checks of the frozen support rubric, not human gold.

Ten fictitious fact families, six source conditions each. Generated and frozen
before model calls; designed after field judgments, with no subsequent tuning.
"""
from __future__ import annotations
import argparse,collections,concurrent.futures,hashlib,json,random
from datetime import datetime,timezone
from pathlib import Path
import newwave_judge_support as judge
ROOT=Path(__file__).resolve().parents[1]
R=ROOT/'results'
T=ROOT/'tmp/newwave_controlled_support'

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def generate():
    rows=[];gold={}
    for i in range(10):
        name=f'Fictional-Protocol-{i+31}'
        day=f'2026-04-{i+11:02d}'
        nextday=f'2026-04-{i+12:02d}'
        if i<6:
            claim=f'{name} was enabled on {day}.'
            texts=[f'Complete audit record. {claim} End of entry.',f'Complete audit record. {name} was enabled sometime in April 2026. The day of the month is not recorded. End of entry.',f'Complete public directory. {name} is the name of a fictitious protocol. The contact desk is on the second floor. This entry only describes the desk location. End of entry.',f'Complete audit record. {name} was not enabled on {day}. It was enabled on {nextday}. End of entry.','','Sign in to read the full audit record. Subscriber preview only.']
        elif i<8:
            claim=f'架空のプロトコル{name}は{day}に有効化された。'
            texts=[f'完全な監査記録。{claim}記録はここで終わる。',f'完全な監査記録。架空のプロトコル{name}は2026年4月中に有効化された。具体的な日は記録されていない。記録はここで終わる。',f'完全な案内文。{name}は架空のプロトコルの名称である。問い合わせ窓口は2階にある。この案内文は窓口の場所だけを説明する。',f'完全な監査記録。架空のプロトコル{name}は{day}には有効化されなかった。{nextday}に有効化された。記録はここで終わる。','','監査記録の全文を読むにはログインしてください。購読者向け記事のプレビューです。']
        else:
            claim=f'El protocolo ficticio {name} se activó el {day}.'
            texts=[f'Registro de auditoría completo. {claim} Fin del registro.',f'Registro de auditoría completo. El protocolo ficticio {name} se activó en abril de 2026. El día exacto no está registrado. Fin del registro.',f'Directorio público completo. {name} es el nombre de un protocolo ficticio. El mostrador de información está en la segunda planta. Esta entrada solo describe su ubicación.',f'Registro de auditoría completo. El protocolo ficticio {name} no se activó el {day}. Se activó el {nextday}. Fin del registro.','','Inicie sesión para leer el registro completo. Solo se muestra un avance para suscriptores.']
        for condition,(text,label) in enumerate(zip(texts,['FULL','PARTIAL','NONE','CONTRADICTS','UNASSESSABLE','UNASSESSABLE'])):
            rows.append({'family':i,'condition':condition,'gold':label,'packet':{'note_text':claim,'fixed_main_claim':claim,'other_material_claims_not_scored':[],'original_post_or_media_available':False,'sources':[{'source_id':'S1','citation_urls':['https://example.invalid/fictional-audit-record'],'final_url':'https://example.invalid/fictional-audit-record','status_code':200,'fetch_status':'synthetic_control_no_request','fetched_utc':None,'format':'html','title':claim if condition==5 else 'Fictitious audit or directory record','main_selector':'synthetic complete text or explicitly empty/teaser','main_text':text,'coverage':{'input_chars':len(text),'extracted_chars_total':len(text),'input_truncated':False,'body_capped_2mb':False,'pdf_pages_extracted':None,'pdf_page_count':None},'body_sha256':hashlib.sha256(text.encode()).hexdigest(),'main_text_saved_sha256':hashlib.sha256(text.encode()).hexdigest()}]}})
    random.Random(2026111517).shuffle(rows)
    packet=[]
    for j,row in enumerate(rows,1):
        code=f'C{j:03d}';row['packet']['code']=code;packet.append(row['packet']);gold[code]={k:row[k] for k in ('family','condition','gold')}
    return packet,gold

def prepare():
    packet,gold=generate()
    assert len(packet)==60 and len(gold)==60
    dest=R/'newwave_controls'
    dest.mkdir(exist_ok=True)
    for name,obj in [('packet.json',packet),('gold.json',gold)]:
        p=dest/name
        if p.exists():raise FileExistsError(p)
        p.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    protocol={'schema':'controlled-support-quality-check-v1','prepared_utc':datetime.now(timezone.utc).isoformat(),'status':'Prepared before control model calls; conceived after field labels, not a preregistration of field outcomes.','families':10,'conditions_per_family':6,'cases':60,'languages':{'English_families':6,'Japanese_families':2,'Spanish_families':2},'gold_rule':'Exact enabled date FULL; month but no day PARTIAL; unrelated complete directory NONE; explicit not-on-date plus next-day CONTRADICTS; empty source or title-only subscriber teaser UNASSESSABLE. Gold concerns entailment in fictitious text, not outside factual truth.','model_rule':'Identical frozen prompt/schema and official CLI configuration as field support judgments. Gold/family/condition not passed to model. No tools, fitting or tuning. One attempt per case; invalid execution not credited as correct. Preserve all 60.','analysis':'Raw and strict confusion matrices, exact correctness by gold class and family; no independence-based confidence interval across repeated families. Strict quote-invalid outputs become UNASSESSABLE, technical failures score incorrect. Controls test only simple known transformations; cannot establish real-source semantic accuracy.','hashes':{'packet':sha(dest/'packet.json'),'gold':sha(dest/'gold.json'),'script':sha(Path(__file__)),'frozen_judge_script':sha(Path(judge.__file__)),'prompt':hashlib.sha256(judge.PROMPT.encode()).hexdigest(),'schema':hashlib.sha256(json.dumps(judge.SCHEMA,sort_keys=True).encode()).hexdigest()}}
    (dest/'protocol.json').write_text(json.dumps(protocol,indent=2)+'\n',encoding='utf8')
    print(json.dumps(protocol,indent=2))

def run():
    dest=R/'newwave_controls';p=json.loads((dest/'protocol.json').read_text(encoding='utf8'))
    assert p['hashes']['script']==sha(Path(__file__)) and p['hashes']['packet']==sha(dest/'packet.json') and p['hashes']['gold']==sha(dest/'gold.json') and p['hashes']['frozen_judge_script']==sha(Path(judge.__file__))
    packet=json.loads((dest/'packet.json').read_text(encoding='utf8'))
    T.mkdir(exist_ok=True);judge.T=T
    schema=T/'schema.json';schema.write_text(json.dumps(judge.SCHEMA,indent=2)+'\n',encoding='utf8')
    output=dest/'trials.jsonl'
    if output.exists():raise FileExistsError(output)
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool,output.open('w',encoding='utf8') as h:
        for result in pool.map(lambda row:judge.trial(row,schema),packet):
            h.write(json.dumps(result,ensure_ascii=False)+'\n');h.flush()
            print(result['code'],result['valid_execution'],(result.get('response') or {}).get('main_claim_verdict'),result.get('quote_validation_errors'),flush=True)
    gold=json.loads((dest/'gold.json').read_text(encoding='utf8'))
    results=[json.loads(s) for s in output.read_text(encoding='utf8').splitlines()]
    assert len(results)==60
    stats={}
    for strict in (False,True):
        confusion=collections.Counter();correct=0;by=collections.defaultdict(lambda:collections.Counter())
        for r in results:
            expected=gold[r['code']]['gold'];valid=r['valid_execution'];pred=r.get('response',{}).get('main_claim_verdict') if valid else 'EXECUTION_FAILURE'
            if strict and valid and r.get('quote_validation_errors'):pred='UNASSESSABLE'
            confusion[(expected,pred)]+=1;correct+=valid and pred==expected;by[expected]['total']+=1;by[expected]['correct']+=valid and pred==expected
        stats['strict' if strict else 'raw']={'correct':correct,'total':60,'confusion':{f'{a}__{b}':n for (a,b),n in sorted(confusion.items())},'by_gold':dict(by)}
    summary={'analysis_kind':'synthetic_known_answer_support_rubric_controls','families':10,'cases':60,'valid_executions':sum(r['valid_execution'] for r in results),'model_advertised_counts':dict(collections.Counter(r.get('model_advertised') for r in results)),'results':stats,'hashes':{'trials':sha(output),'protocol':sha(dest/'protocol.json'),'packet':sha(dest/'packet.json'),'gold':sha(dest/'gold.json')},'interpretation':'Known transformations in fictitious text; separate post-field quality check, no human validation or estimate of field accuracy. Repeated families are not independent observations.'}
    (dest/'aggregate.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf8')
    print(json.dumps(summary,indent=2))

if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('mode',choices=['prepare','run']);args=a.parse_args()
    prepare() if args.mode=='prepare' else run()
