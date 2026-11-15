"""Public-safe aggregate of fixed-claim source-support diagnostics.

Private case records never enter the public aggregate. Retries replace only
technically incomplete journal records under the prospective amendment.
"""
import collections
import hashlib
import json
import math
import random
from pathlib import Path

import newwave_judge_support as base

ROOT = Path(__file__).resolve().parents[1]
R = ROOT / 'results'
LABELS = ['FULL', 'PARTIAL', 'NONE', 'CONTRADICTS', 'UNASSESSABLE']
GROUPS = ['AI_API', 'non_API']
BOOTSTRAP_SEED = 2026111514
BOOTSTRAP_DRAWS = 10000


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def jsonl(path):
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()]


def percentile(values, p):
    a = sorted(values)
    k = (len(a) - 1) * p
    lo, hi = math.floor(k), math.ceil(k)
    return a[lo] + (a[hi] - a[lo]) * (k - lo)


def wilson(successes, n):
    z = 1.959963984540054
    p = successes / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [c - h, c + h]


def agreement(primary, recode):
    matrix = {a: {b: 0 for b in LABELS} for a in LABELS}
    for code, second in recode.items():
        matrix[primary[code]][second] += 1
    n = len(recode)
    agrees = sum(matrix[label][label] for label in LABELS)
    po = agrees / n
    expected = sum(sum(matrix[label].values()) * sum(matrix[a][label] for a in LABELS)
                   for label in LABELS) / (n * n)
    return {'n': n, 'exact_agreement_n': agrees, 'exact_agreement_rate': po,
            'agreement_wilson_95_descriptive': wilson(agrees, n),
            'cohen_kappa': (po - expected) / (1 - expected) if expected != 1 else None,
            'chance_expected_agreement': expected,
            'confusion_matrix_rows_primary_columns_independent_AI': matrix,
            'human_gold_standard': False}


def summarize(labels, group_by_code, pair_codes, authors):
    groups = {}
    for group in GROUPS:
        counts = collections.Counter(labels[code] for code, g in group_by_code.items() if g == group)
        n = sum(counts.values())
        groups[group] = {'n': n, 'label_counts': {label: counts[label] for label in LABELS},
                         'label_rates': {label: counts[label] / n for label in LABELS},
                         'FULL_or_PARTIAL_n': counts['FULL'] + counts['PARTIAL'],
                         'FULL_or_PARTIAL_rate': (counts['FULL'] + counts['PARTIAL']) / n}
    predicates = {label: {label} for label in LABELS}
    predicates['FULL_or_PARTIAL'] = {'FULL', 'PARTIAL'}
    rng = random.Random(BOOTSTRAP_SEED)
    indices = [[rng.randrange(len(pair_codes)) for _ in pair_codes] for _ in range(BOOTSTRAP_DRAWS)]
    paired = {}
    for metric, positive in predicates.items():
        cells = collections.Counter()
        deltas = []
        by_author = collections.defaultdict(list)
        for pair in pair_codes:
            a, b = int(labels[pair['AI_API']] in positive), int(labels[pair['non_API']] in positive)
            cells[(a, b)] += 1
            deltas.append(a - b)
            by_author[authors[pair['AI_API']]].append(a - b)
        n = len(deltas)
        bootstrap = [sum(deltas[i] for i in sample) / n for sample in indices]
        total = sum(deltas)
        loo = [(total - sum(values)) / (n - len(values)) for values in by_author.values() if len(values) < n]
        paired[metric] = {'pairs': n, 'AI_API_minus_non_API': total / n,
                          'discordance': {'both': cells[(1, 1)], 'AI_API_only': cells[(1, 0)],
                                          'non_API_only': cells[(0, 1)], 'neither': cells[(0, 0)]},
                          'post_pair_bootstrap_95_descriptive': [percentile(bootstrap, .025), percentile(bootstrap, .975)],
                          'equal_AI_author_average_difference': sum(sum(v) / len(v) for v in by_author.values()) / len(by_author),
                          'leave_one_AI_author_out_difference_range': [min(loo), max(loo)] if loo else None}
    return {'by_group': groups, 'paired_differences': paired}


def main():
    paths = {name: R / filename for name, filename in {
        'packet': 'newwave_support_packet_blind.json',
        'original_journal': 'newwave_support_trials_PRIVATE.jsonl',
        'retry_journal': 'newwave_support_retry_trials_PRIVATE.jsonl',
        'technical_amendment': 'newwave_support_retry_amendment_PRIVATE.json',
        'key': 'newwave_semantic_key_PRIVATE.json',
        'independent_recode': 'newwave_support_recode20.jsonl',
        'recode_selection': 'newwave_support_recode20_freeze.json',
        'contradiction_review': 'newwave_support_contradiction_review_PRIVATE.json',
        'alignment': 'newwave_alignment_trials_PRIVATE.jsonl',
        'candidates': 'revision_samepost_candidates_v2_PRIVATE.jsonl'}.items()}
    amendment = json.loads(paths['technical_amendment'].read_text(encoding='utf-8'))
    for rel, expected in amendment['frozen_inputs_sha256'].items():
        assert sha(ROOT / rel) == expected, rel
    for rel, expected in amendment['original_retry_artifacts_sha256'].items():
        assert sha(ROOT / rel) == expected, rel
    packet = json.loads(paths['packet'].read_text(encoding='utf-8'))
    rows = {row['code']: row for row in packet}
    original = jsonl(paths['original_journal'])
    retries = jsonl(paths['retry_journal'])
    assert len(rows) == len(packet) == 200
    assert len(original) == 186 and sum(r['valid_execution'] for r in original) == 185
    assert len(retries) == len({r['code'] for r in retries}) == 15
    assert {r['code'] for r in retries} == set(amendment['retry_codes'])
    selected = {r['code']: r for r in original if r['valid_execution']}
    assert not set(selected) & {r['code'] for r in retries}
    selected.update({r['code']: r for r in retries})
    assert set(selected) == set(rows)
    key = json.loads(paths['key'].read_text(encoding='utf-8'))
    group_by_code = {pair['code'] + side: group for pair in key for side, group in pair['groups'].items()}
    pair_codes = [{group: pair['code'] + side for side, group in pair['groups'].items()} for pair in key]
    assert len(pair_codes) == 100 and set(group_by_code) == set(rows)
    note_authors = {str(note['note_id']): str(note['author_id']) for candidate in jsonl(paths['candidates'])
                    for note in [candidate['ai'], candidate['non_api']]}
    authors = {pair['code'] + side: note_authors[str(note)] for pair in key for side, note in pair['sides'].items()}
    raw, strict, diagnostics = {}, {}, []
    role_counts = {group: collections.Counter() for group in GROUPS}
    substance_counts = {group: collections.Counter() for group in GROUPS}
    coverage = {group: collections.Counter() for group in GROUPS}
    validation_counts = collections.Counter()
    saved_error_mismatches = []
    for code, row in rows.items():
        execution = selected[code]
        valid = execution['valid_execution']
        response = execution.get('response') if valid else None
        errors = base.validate_result(response, row) if response else ['invalid_execution']
        if valid and errors != execution['quote_validation_errors']:
            saved_error_mismatches.append(code)
        label = response['main_claim_verdict'] if response else 'UNASSESSABLE'
        raw[code] = label
        strict[code] = 'UNASSESSABLE' if errors else label
        group = group_by_code[code]
        for error in errors:
            validation_counts[error.split(':', 1)[0]] += 1
        source_by_id = {s['source_id']: s for s in row['sources']}
        for observation in response['source_observations'] if response else []:
            role_counts[group][observation['source_role']] += 1
            substance_counts[group]['substantive' if observation['substantive_text_observed'] else 'not_substantive'] += 1
            if observation['source_role'] == 'SUPPORT' and observation['substantive_text_observed']:
                substance_counts[group]['SUPPORT_and_substantive'] += 1
        flags = coverage[group]
        flags['notes'] += 1
        flags['source_slots'] += len(row['sources'])
        flags['notes_all_sources_empty'] += int(all(not s['main_text'] for s in row['sources']))
        flags['notes_any_empty_source'] += int(any(not s['main_text'] for s in row['sources']))
        flags['notes_any_input_truncation'] += int(any(s['coverage']['input_truncated'] for s in row['sources']))
        flags['notes_any_body_cap'] += int(any(s['coverage']['body_capped_2mb'] for s in row['sources']))
        if response:
            flags['notes_all_sources_model_non_substantive'] += int(not any(s['substantive_text_observed'] for s in response['source_observations']))
        for source in row['sources']:
            flags['empty_main_text_slots'] += int(not source['main_text'])
            flags['input_truncated_slots'] += int(source['coverage']['input_truncated'])
            flags['body_capped_2mb_slots'] += int(source['coverage']['body_capped_2mb'])
            flags['pdf_slots'] += int(source['format'] == 'pdf')
            flags['policy_unassessable_slots'] += int(source['fetch_status'] == 'policy_unassessable')
            flags['non_http_response_slots'] += int(source['fetch_status'] != 'http_response')
        diagnostics.append({'code': code, 'group': group, 'origin': 'retry' if code in amendment['retry_codes'] else 'original',
                            'valid_execution': valid, 'raw_label': label, 'strict_label': strict[code],
                            'validation_errors': errors, 'evidence_items': len(response['evidence']) if response else 0,
                            'source_count': len(source_by_id)})
    assert not saved_error_mismatches
    positive = [r for r in diagnostics if r['raw_label'] in {'FULL', 'PARTIAL', 'CONTRADICTS'}]
    invalid_quotes = [r for r in positive if r['validation_errors']]
    assert all(r['strict_label'] == 'UNASSESSABLE' for r in invalid_quotes)
    contradiction_review = json.loads(paths['contradiction_review'].read_text(encoding='utf-8'))
    reviewed_cases = contradiction_review['cases']
    contradiction_codes = {r['code'] for r in diagnostics if r['raw_label'] == 'CONTRADICTS'}
    assert {r['private_packet_code'] for r in reviewed_cases} == contradiction_codes
    assert all(raw[code] == strict[code] == 'CONTRADICTS' for code in contradiction_codes)
    recodes = jsonl(paths['independent_recode'])
    recode = {r['code']: r['label'] for r in recodes}
    selection = json.loads(paths['recode_selection'].read_text(encoding='utf-8'))
    assert len(recode) == 20 and set(recode) == set(selection['codes'])
    for record in recodes:
        wc = collections.Counter()
        source_map = {s['source_id']: s for s in rows[record['code']]['sources']}
        for e in record['evidence']:
            assert e['quote'] in source_map[e['source_id']]['main_text']
            wc[e['source_id']] += len(e['quote'].split())
        assert all(n <= 20 for n in wc.values())
    alignment = {r['code']: r['response']['relation'] for r in jsonl(paths['alignment'])}
    by_alignment = {}
    for category in sorted(set(alignment.values())):
        subset = {code for code in rows if alignment[code[:-1]] == category}
        by_alignment[category] = {'pairs': len(subset) // 2,
            'strict_label_counts_by_group': {g: {label: sum(strict[c] == label for c in subset if group_by_code[c] == g)
                                               for label in LABELS} for g in GROUPS}}
    author_summary = {}
    for group in GROUPS:
        counts = collections.Counter(authors[c] for c, g in group_by_code.items() if g == group)
        values = sorted(counts.values(), reverse=True)
        n = sum(values)
        author_summary[group] = {'distinct_accounts': len(values), 'top_1_note_share': values[0] / n,
                                 'top_10_note_share': sum(values[:10]) / n,
                                 'effective_accounts_inverse_hhi': 1 / sum((v / n) ** 2 for v in values)}
    result = {
        'analysis_kind': 'AI_assisted_fixed_claim_all_citation_source_support_diagnostic',
        'sample': {'post_pairs': 100, 'notes': 200, 'notes_per_group': 100,
                   'source_slots': 357, 'distinct_collected_network_urls': 319,
                   'original_post_or_media_available_notes': sum(r['original_post_or_media_available'] for r in packet)},
        'execution': {'original_journal_records': len(original), 'original_valid_used': 185,
                      'original_timeout_records_preserved': 1, 'original_unjournaled_completion_sets_preserved_not_used': 14,
                      'prospective_retry_attempts': len(retries), 'retry_valid': sum(r['valid_execution'] for r in retries),
                      'retry_invalid_as_UNASSESSABLE': sum(not r['valid_execution'] for r in retries),
                      'selected_model_advertised_counts': dict(collections.Counter(r.get('model_advertised', 'unavailable') for r in selected.values())),
                      'technical_amendment_public_commit': amendment['public_protocol_commit']},
        'raw': summarize(raw, group_by_code, pair_codes, authors),
        'strict': summarize(strict, group_by_code, pair_codes, authors),
        'strict_rule': 'Any invalid execution or literal-evidence/source-coverage validation failure is UNASSESSABLE; original raw records are unchanged.',
        'validation_audit': {'all_selected_cases_revalidated': len(selected),
                             'evidence_positive_or_contradicts_cases_checked': len(positive),
                             'evidence_positive_or_contradicts_cases_with_validation_error': len(invalid_quotes),
                             'all_such_errors_flagged_and_strict_downgraded': True,
                             'saved_vs_recomputed_error_mismatches': 0,
                             'cases_with_any_validation_error': sum(bool(r['validation_errors']) for r in diagnostics),
                             'error_event_counts': dict(validation_counts),
                             'raw_to_strict_downgrade_counts': dict(collections.Counter(r['raw_label'] for r in diagnostics if r['raw_label'] != r['strict_label']))},
        'source_role_diagnostics': {group: {'role_counts': dict(role_counts[group]),
                                           'substantive_observation_counts': dict(substance_counts[group])} for group in GROUPS},
        'independent_contradiction_packet_review': {
            'reviewer_type': 'independent_root_AI_packet_review',
            'complete_packets_reviewed': len(reviewed_cases),
            'robust_factual_contradictions_confirmed': sum(r['confirmed_contradiction'] for r in reviewed_cases),
            'raw_model_CONTRADICTS_labels_retained': len(contradiction_codes),
            'strict_model_CONTRADICTS_labels_retained': len(contradiction_codes),
            'model_labels_changed_by_review': 0,
            'interpretation': 'No independently confirmed contradiction was established from these supplied packets; technical quote validity does not establish logical opposition or note falsehood.',
            'private_case_reasons_withheld': True, 'human_gold_standard': False},
        'coverage': {group: dict(coverage[group]) for group in GROUPS},
        'independent_AI_recode': {'frozen_before_primary_comparison': True,
                                  'raw_primary': agreement(raw, recode), 'strict_primary': agreement(strict, recode),
                                  'independent_recode_label_counts': dict(collections.Counter(recode.values()))},
        'alignment_strata_diagnostic_only': by_alignment,
        'account_concentration': author_summary,
        'uncertainty': {'method': 'Post-pair percentile bootstrap, retaining both cohort notes together; descriptive sensitivity only',
                        'draws': BOOTSTRAP_DRAWS, 'seed': BOOTSTRAP_SEED,
                        'account_sensitivity': 'Equal-AI-account means and leave-one-AI-account-out ranges change or perturb the post-weighted estimand.',
                        'not_captured': 'Systematic model mistakes, model dependence, source extraction/censoring, nonrandom source choice, and conditional-frame selection are not resolved by bootstrap intervals.'},
        'input_sha256': {name: sha(path) for name, path in paths.items()},
        'analysis_script_sha256': sha(Path(__file__)),
        'limitations': ['AI-vs-AI reliability diagnostic, not human gold or factual truth certification.',
                        'Current static retrieved text support, not historical availability or semantic drift.',
                        'Source roles describe intended citation roles, not truth or authority.',
                        'A literal quote can still fail to entail a fixed claim; strict validation is necessary, not sufficient.',
                        'Original posts/media are unavailable; exact visual identity cannot be inferred from unspecified background articles.',
                        'Same-post pairs may make different corrections; alignment labels also showed limited recode reliability.',
                        'Observed API enrollment is not proof of AI composition; non-API is not verified human writing.',
                        'Conditional currently-Helpful same-post sample, not a causal authorship effect or population-wide rate.']}
    (R / 'newwave_support_analysis.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    (R / 'newwave_support_case_diagnostics_PRIVATE.json').write_text(json.dumps(diagnostics, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'raw_group_counts': {g: result['raw']['by_group'][g]['label_counts'] for g in GROUPS},
                      'strict_group_counts': {g: result['strict']['by_group'][g]['label_counts'] for g in GROUPS},
                      'validation_audit': result['validation_audit'],
                      'recode_raw_agreement': result['independent_AI_recode']['raw_primary']['exact_agreement_n'],
                      'recode_strict_agreement': result['independent_AI_recode']['strict_primary']['exact_agreement_n'],
                      'contradiction_codes_PRIVATE': [r['code'] for r in diagnostics if r['raw_label'] == 'CONTRADICTS']}))


if __name__ == '__main__':
    main()
