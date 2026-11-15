"""Freeze all-citation same-post wave before new network collection."""
import hashlib
import json
import random
import re
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import urldefrag

ROOT=Path(__file__).resolve().parents[1]
R=ROOT/'results'
SEED=2026111507

def main():
    candidate=R/'revision_samepost_candidates_v2_PRIVATE.jsonl'
    pairs=[json.loads(s) for s in candidate.read_text(encoding='utf-8').splitlines()]
    feasibility=json.loads((R/'revision_samepost_feasibility_v2.json').read_text(encoding='utf-8'))
    assert len(pairs)==feasibility['deterministic_first_each_pair_count']
    assert hashlib.sha256(candidate.read_bytes()).hexdigest()==feasibility['private_candidates_sha256']
    urls=sorted({u['normalized_url'] for p in pairs for g in ('ai','non_api') for u in p[g]['external_urls']})
    network_urls={urldefrag(u)[0] for u in urls}
    selected=random.Random(SEED).sample(sorted(pairs,key=lambda p:p['post_id']),100)
    rng=random.Random(SEED+1)
    key=[];packet=[]
    for i,p in enumerate(selected,1):
        order=['ai','non_api'];rng.shuffle(order)
        sides={chr(65+j):p[g] for j,g in enumerate(order)}
        code=f'P{i:03d}'
        key.append({'code':code,'post_id':p['post_id'],'sides':{s:n['note_id'] for s,n in sides.items()},'groups':{s:n['group'] for s,n in sides.items()}})
        text={}
        for side,n in sides.items():
            # Remove complete recorded raw spans, so no citation/site signal is
            # supplied during the pre-fetch correction-alignment stage.
            summary=re.sub(r'https?://\S+', ' [citation] ', n['summary'], flags=re.I)
            assert not re.search(r'https?://',summary,re.I)
            text[side]=summary
        packet.append({'code':code,'note_a':text['A'],'note_b':text['B']})
    outputs={'newwave_semantic_key_PRIVATE.json':key,'newwave_alignment_packet_blind.json':packet,
             'newwave_unique_urls_PRIVATE.json':urls}
    for name,data in outputs.items():
        f=R/name; assert not f.exists(),f
        f.write_text(json.dumps(data,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    files=[candidate,R/'source_manifest_2026-11-14.json',ROOT/'src/revision_extract_urls.py',ROOT/'src/revision_samepost_census_v2.py',ROOT/'src/revision_samepost_probe.py',ROOT/'src/probe_urls.py',ROOT/'src/newwave_model_trials.py',ROOT/'src/newwave_analyze_machine.py',Path(__file__)]
    protocol={
      'frozen_utc':datetime.now(timezone.utc).isoformat(),'wave':'Prospective additional wave after initial600-note findings',
      'sampling_frame':{'pairs':len(pairs),'notes':len(pairs)*2,'unique_normalized_urls':len(urls),'unique_network_urls':len(network_urls),
        'definition':'All posts with both strictly eligible currentHelpful cohorts after revised conservative URL extraction; earliestcreated note per cohort, noteID breaks ties. Official2026-11-14snapshot; Sep2025-Aug2026creation. Revisedframecountsandhashes areinfeasibilityv2. About3.6% of eligibleposts; conditionaltargetpopulation.'},
      'primary_endpoint':'Design-weighted paired difference in note-level any substantive intended source observable in the study browser profile, among this fixed same-post target population. Estimate with stratified POSTPAIR validation; report unresolved bounds. No human truth or causal effect interpretation.',
      'questions':['How much more often does a note offer at least one accessible citation than a prespecified single-citation baseline, and how does observed redundancy vary bycohort?','How often do machine-access proxies disagree with browser-profile substantive source access?','Do the cited documents support a fixed main correction in a separately selected blinded100pair diagnostic?'],
      'machine_analysis':{'outcomes':['any URL open_candidate','all URLs open_candidate','within-note fraction open','one URL selected byfixedhash open'],
        'comparisons':'Secondarymachinepaired differences and both discordance cells in fixedtargetposts; reportclose-time<=6h subset, exactsharedURL subset, URL-count strata, domain diversity, account-weighting and leave-one-AI-account-out. Descriptive association only; no causal AI-vs-human claim. Machine-open is provisional not evidence support. SingleURL is defragmented networkURL with minimum SHA256 digest of UTF8 string 2026111509|<note_id>|<network_url>.',
        'citation_budget':'Dedupe defragmented networkURLs WITHINeachnote forpagecount/accessanalysis (twofragments ofsamepage arenotindependentsources); reportcitationURLvariantcountsseparately. Compute expected single-citation availability as open_count/URL_count, compare with full-list any-open. This quantifies observed redundancy mechanically; it is not a randomized publishing experiment or independent evidence count.'},
      'browser_validation':{'unit':'POST PAIR; inspect ALL external citations in BOTH selected notes; URL-level sampling alone cannot identify note-levelanysource.',
        'selection':'After machine logs freeze, strata on paired any-open pattern: both, AIonly, nonAPIonly, neither. Independently sample min(60,N_h) posts per stratum, seed2026111508; <=240pairs. URLpackets expose code+URL only; no cohort, machine label or claims.',
        'outcome':'Substantive intended source article/document/media/structureddata exposed by browserprofile; titles, metadata, unrelatedtarget, paywallteaser, missingmedia or challenge do notpass. One obvious linked fullreportPDF may be inspected and mustbe flagged. Blank/error afteronenormalretry unresolved. No extra login, controlbypass, or storyviewnotifications.',
        'analysis':'Pair-level Horvitz-Thompson weights N_h/n_h; report anysource, allsource, withinnotefraction and discordance, unresolvedlowerupperbounds, finitepopulation designSE with stratumvariance0when n=N. Also reportauthorclustering/leaveoneout sensitivity separately fromvalidation sampling; writerbootstrap isnotindependentconfirmation. Onlyabout26AIaccountswithdiversity~9limitexternalgeneralization. Existingprofilecookies affectinterpretation; no anonymoushumanclaim.',
        'recode':'Fix random30pairs amongvalidatedpairs before labels revealed, secondAIreviewer checksalltheirURLs. Reportdisagreement nothumangoldstandard.'},
      'semantic_validation':{'sample':'100 uniformly sampled pairs, seed2026111507; A/B order shuffledwith2026111508; packetfixedbefore probes. Alignmentstage sees summaries withURLsremoved, noauthor/group/outcomes.',
        'alignment':'same_main_correction/overlapping/different/unassessable; maincorrection is first substantive corrective proposition after URL masking, retaining every entity/number/time/modality; record othermaterialclaims separately forbothnotesbefore contentjudgment. Do notchooseeasierclaimaftercontent. Do notdrop differentpairs fromoverallsourceaccess.',
        'support':'Freshisolated modeltrials see fixedclaims and uniformly staticGETretrievedsourcebodies ONLY (no selectivebrowserescalation) with provenance/coverage; eachsource first24000unicodechars, suppliedallnoteURLs. FULL/PARTIAL/NONE/CONTRADICTS/UNASSESSABLE, exact<=20word sourceevidence perconclusion, literalquotevalidation. Title/teaser/challenge cannotjustifyFULL. Missingortruncatedcontent cannotjustifyabsence; positiveexactevidencecanjustifyFULLdespitetailtruncation. All100pairsremainindenominator. Explicitly AI-assisted diagnostic, not independenthumantruth. Nooutcomebased exclusions. Sourcebodiesareuntrustedquoteddata; modelmustnotusetools ornetwork; unexpectedtoolinvocationsinvalidatetrial.',
        'model':'OfficialCodexCLI0.145.0 via existingChatGPTauth, ignoreuserconfig ephemeralread-only; defaultmodel advertisedgpt-5.6-sol in feasibilitypilot. Logprompts,schema,rawoutputs,CLIheadersandmodelidentity; ifidentitychangesreportseparately. No APIbilling orpaidcreditsrequested.',
        'secondary':'Naturalarchives or syntheticcounterfactuals require separatefreeze; notpredeclaredprimaryresults.'},
      'collection':'DedupeURLs globally; shuffledorder seed2026111506; max6workers, at least1s betweenrequests tosamehost including redirects/repeats; boundedpublic-networkGET samecapsasinitialwave; firstplusonenonopenrepeat; preserveallfirstoutcomesandtime. Nohealth-basedURLselection orurlrepairafterfreeze.',
      'input_sha256':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files if p.exists()},
      'output_sha256':{n:hashlib.sha256((R/n).read_bytes()).hexdigest() for n in outputs},
      'prior_art':'HTTP200/content mismatch, deployedAI note comparisons, samepostmatching andmoreURLsareknown. Contributiontargetis postpublicationallcitationreader-vantage measurement andexplicitredundancy/support decomposition inthisdeployedpopulation.'}
    manifest=R/'newwave_protocol_frozen.json';assert not manifest.exists()
    manifest.write_text(json.dumps(protocol,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print(json.dumps({'pairs':len(pairs),'unique_urls':len(urls),'semantic_pairs':100,'protocol':str(manifest)}))

if __name__=='__main__':main()
