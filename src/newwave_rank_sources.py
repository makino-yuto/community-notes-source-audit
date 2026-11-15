"""Exploratory offline citation-priority benchmark, with no fitting or network.

Specified after browser observations were seen; not preregistered and not an
intervention on readers. The earlier machine labels alone determine ranking.
"""
from __future__ import annotations
import argparse,hashlib,json
from datetime import datetime,timezone
from pathlib import Path
from newwave_analyze_browser import verify_freeze,load_labels,estimate,GROUPS,STRATA
from newwave_analyze_machine import digest_file
ROOT=Path(__file__).resolve().parents[1]
R=ROOT/'results'

def bounds(code,labels):
    y=labels[code]['outcome']
    return (1.,1.) if y=='accessible' else ((0.,0.) if y=='not_accessible' else (0.,1.))

def gain_bounds(codes,selected,labels):
    """Sharp linear bounds sharing the same unknown URL across both policies."""
    n=len(codes);lo=hi=point=0.
    for code in codes:
        coefficient=float(code==selected)-1/n
        lower,upper=bounds(code,labels)
        point+=coefficient*lower
        lo+=min(coefficient*lower,coefficient*upper)
        hi+=max(coefficient*lower,coefficient*upper)
    return lo,hi,point

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output',type=Path,default=R/'newwave_ranking_exploratory.json')
    a=ap.parse_args()
    if a.output.exists():raise FileExistsError(a.output)
    freeze,key,expected=verify_freeze(R/'newwave_browser_freeze.json',R/'newwave_browser_key_PRIVATE.json')
    paths=[R/'newwave_browser_a_normalized.jsonl',R/'newwave_browser_b.jsonl',R/'newwave_browser_c_normalized.jsonl']
    labels=load_labels(paths,expected)
    lookup={r['code']:r['url'] for r in key['url_lookup']}
    rows=[]
    for pair in key['selected_pairs']:
        groups={}
        for group in GROUPS:
            item=pair['groups'][group];codes=item['network_url_codes']
            def order(code):
                raw=f"2026111509|{item['note_id']}|{lookup[code]}".encode('utf8')
                return hashlib.sha256(raw).hexdigest(),lookup[code]
            baseline=min(codes,key=order)
            candidates=[c for c in codes if item['machine_categories'][c]=='open_candidate']
            selected=min(candidates,key=order) if candidates else baseline
            lower,upper=bounds(selected,labels);b_lo,b_hi=bounds(baseline,labels)
            g_lo,g_hi,point=gain_bounds(codes,selected,labels)
            groups[group]={
                'prioritized_lower':lower,'prioritized_upper':upper,
                'fixed_hash_lower':b_lo,'fixed_hash_upper':b_hi,
                'uniform_lower':sum(bounds(c,labels)[0] for c in codes)/len(codes),
                'uniform_upper':sum(bounds(c,labels)[1] for c in codes)/len(codes),
                'priority_gain_vs_uniform_lower':g_lo,'priority_gain_vs_uniform_upper':g_hi,
                'priority_gain_vs_uniform_unknown_zero':point,
                'machine_positive_coverage':float(bool(candidates)),
                'abstaining_priority_success_lower':lower*bool(candidates),
                'abstaining_priority_success_upper':upper*bool(candidates),
                'selected_differs_from_hash':float(selected!=baseline),
            }
        rows.append({'stratum':pair['stratum'],'groups':groups})
    fields=tuple(rows[0]['groups']['AI_API'])
    out={
        'analysis_kind':'exploratory_deterministic_offline_citation_priority',
        'created_utc':datetime.now(timezone.utc).isoformat(),
        'prospective_status':'Exploratory, specified after browser observations and overall results; no preregistration claim, fitting, parameter search, or outcome-based link choice.',
        'policy':'Minimum frozen SHA-256 rank among machine open_candidates, or original minimum-hash link if no candidate. Optional abstaining variant offers no link in that case.',
        'baseline':'Expected success of one uniformly chosen distinct network citation and the original fixed-hash citation.',
        'interpretation':'Offline access comparison in the same browser-label sample; not a reader intervention, factual verification, or independent-source evidence.',
        'target_pairs':1882,'sample_pairs':len(rows),'browser_urls':len(labels),
        'input_sha256':{'script':digest_file(Path(__file__)),'freeze':digest_file(R/'newwave_browser_freeze.json'),'labels':{p.name:digest_file(p) for p in paths}},
        'groups':{group:{field:estimate({h:[r['groups'][group][field] for r in rows if r['stratum']==h] for h in STRATA},freeze) for field in fields} for group in GROUPS},
        'uncertainty':'Finite-population sampling intervals conditional on AI labels. Gain bounds share each unknown URL across policies. Annotation, time and profile uncertainty are excluded.',
        'cost':'Existing all-citation machine pass; no additional requests. Census used 5,787 URL query units for 3,764 notes.',
    }
    a.output.write_text(json.dumps(out,indent=2)+'\n',encoding='utf8')
    print(json.dumps({g:{f:out['groups'][g][f]['estimate'] for f in ['uniform_lower','uniform_upper','prioritized_lower','prioritized_upper','priority_gain_vs_uniform_lower','priority_gain_vs_uniform_upper','machine_positive_coverage']} for g in GROUPS},indent=2))

if __name__=='__main__':main()
