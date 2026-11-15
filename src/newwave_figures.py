"""Figure 1 from public aggregates only; no case-level data or support funnel.

Example: python src/newwave_figures.py --output-dir output/figures
The thick browser contrast shows conservative bounds, not a confidence interval.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
try:
    import matplotlib
except ImportError:
    sys.path.append(str(ROOT / 'tmp' / 'python-packages'))
    import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.lines import Line2D
from matplotlib.patches import Rectangle

FONTS = ROOT / 'assets' / 'fonts' / 'old-standard-tt'
COLORS = {'AI_API': '#175675', 'non_API': '#965D37'}
DISPLAY = {'AI_API': 'AI-API', 'non_API': 'Non-API'}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def configure_fonts(font_dir: Path):
    for filename in ['OldStandard-Regular.ttf', 'OldStandard-Bold.ttf', 'OldStandard-Italic.ttf']:
        path = font_dir / filename
        if not path.is_file():
            raise FileNotFoundError(f'Missing official Google Fonts Old Standard TT asset: {path}')
        font_manager.fontManager.addfont(str(path))
    plt.rcParams.update({'font.family': 'Old Standard TT', 'font.size': 9,
                         'axes.titlesize': 10, 'axes.labelsize': 9,
                         'xtick.labelsize': 8, 'ytick.labelsize': 9,
                         'pdf.fonttype': 42, 'ps.fonttype': 42,
                         'axes.unicode_minus': False,
                         'axes.spines.top': False, 'axes.spines.right': False,
                         'axes.edgecolor': '#777777', 'axes.linewidth': .55,
                         'savefig.facecolor': 'white', 'text.color': '#111111'})


def make_figure(machine_path: Path, browser_path: Path, output_dir: Path, font_dir: Path):
    machine = json.loads(machine_path.read_text(encoding='utf-8'))
    browser = json.loads(browser_path.read_text(encoding='utf-8'))
    n = machine['frame']['selected_post_pairs']
    assert n == browser['target_population_pairs']
    assert machine['overall']['pairs'] == n
    configure_fonts(font_dir)
    fig = plt.figure(figsize=(6.5, 3.72), layout=None)
    ax_a = fig.add_axes([.125, .265, .335, .535])
    ax_b_group = fig.add_axes([.635, .59, .33, .205])
    ax_b_diff = fig.add_axes([.635, .205, .33, .205])
    fig.text(.025, .94, 'A', fontsize=12, weight='bold')
    fig.text(.075, .94, 'Machine access census', fontsize=11, weight='bold')
    fig.text(.075, .885, f'{n:,} same-post pairs; all cited URLs', fontsize=8.5)
    fig.text(.55, .94, 'B', fontsize=12, weight='bold')
    fig.text(.60, .94, 'AI-assisted browser audit', fontsize=11, weight='bold')
    fig.text(.60, .885, f"{browser['sampled_pairs']:,} sampled pairs; weighted estimates", fontsize=8.5)
    groups = ['AI_API', 'non_API']
    for y, group in zip([1, 0], groups):
        mean = machine['overall']['means'][group]
        uniform, any_open = 100 * mean['open_fraction'], 100 * mean['any_open']
        color = COLORS[group]
        ax_a.plot([uniform, any_open], [y, y], color=color, lw=2, alpha=.55, zorder=2)
        ax_a.scatter([uniform], [y], facecolor='white', edgecolor=color, s=44, lw=1.4, zorder=3)
        ax_a.scatter([any_open], [y], color=color, marker='D', s=37, zorder=3)
        ax_a.annotate(f'{uniform:.1f}', (uniform, y), xytext=(-2, -18), textcoords='offset points', ha='center', fontsize=9)
        ax_a.annotate(f'{any_open:.1f}', (any_open, y), xytext=(1, 10), textcoords='offset points', ha='center', fontsize=9, weight='bold')
    ax_a.set(yticks=[1, 0], yticklabels=[DISPLAY[g] for g in groups], ylim=(-.42, 1.42),
             xlim=(60, 100), xticks=[60, 70, 80, 90, 100], xlabel='Machine-open probability (%)')
    ax_a.grid(axis='x', color='#E5E5E5', lw=.55)
    ax_a.set_axisbelow(True)
    ax_a.spines['left'].set_visible(False)
    ax_a.tick_params(axis='y', length=0, pad=7)
    legend = [Line2D([], [], marker='D', color='#333333', ls='', markersize=5, label='Any cited URL'),
              Line2D([], [], marker='o', markerfacecolor='white', markeredgecolor='#333333', ls='', markersize=5, label='Uniform citation expectation')]
    ax_a.legend(handles=legend, loc='upper left', bbox_to_anchor=(-.22, -.29),
                frameon=False, fontsize=8.5, handlelength=1, borderaxespad=0, labelspacing=.6)

    for y, group in zip([1, 0], groups):
        rates = browser['group_note_outcome_rates'][group]
        lo, hi = 100 * rates['any_lower']['estimate'], 100 * rates['any_upper']['estimate']
        ax_b_group.add_patch(Rectangle((lo, y - .045), hi - lo, .09, color=COLORS[group], zorder=3))
        ax_b_group.plot([lo, hi], [y, y], ls='', marker='|', markersize=8, color=COLORS[group], lw=1)
        ax_b_group.text((lo + hi) / 2, y + .16, f'{lo:.1f}-{hi:.1f}%', ha='center', fontsize=8.5)
    ax_b_group.set(yticks=[1, 0], yticklabels=[DISPLAY[g] for g in groups], ylim=(-.3, 1.5),
                   xlim=(75, 100), xticks=[75, 85, 95, 100])
    ax_b_group.set_title('Any intended source: bounds', loc='left', fontsize=8.6, pad=8)
    ax_b_group.tick_params(axis='y', length=0, pad=5)
    ax_b_group.spines['left'].set_visible(False)
    ax_b_group.set_xlabel('Note fraction (%)', fontsize=8.5, labelpad=2)
    ax_b_group.grid(axis='x', color='#E5E5E5', lw=.55)
    ax_b_group.set_axisbelow(True)

    primary = browser['primary_any_source']
    lower = 100 * primary['partial_identification_lower']['estimate']
    upper = 100 * primary['partial_identification_upper']['estimate']
    outer = [100 * x for x in primary['approx_bonferroni_95_outer_interval_for_identified_set']]
    assert outer[0] <= lower <= upper <= outer[1]
    ax_b_diff.axvline(0, color='#AAAAAA', lw=.7, ls='--', zorder=0)
    ax_b_diff.plot(outer, [0, 0], color='#4D4D4D', lw=1, zorder=1)
    ax_b_diff.plot(outer, [0, 0], ls='', marker='|', markersize=10, color='#4D4D4D')
    ax_b_diff.add_patch(Rectangle((lower, -.07), upper - lower, .14, color='#6B4774', zorder=3))
    ax_b_diff.text((lower + upper) / 2, .28, f'Conservative bounds: {lower:+.1f} to {upper:+.1f}', ha='center', fontsize=8.3, color='#56365E')
    ax_b_diff.text((outer[0] + outer[1]) / 2, -.36, f'95% outer interval: {outer[0]:+.1f} to {outer[1]:+.1f}', ha='center', fontsize=8.2)
    ax_b_diff.set(ylim=(-.65, .65), xlim=(-10, 25), xticks=[-10, 0, 10, 20], yticks=[])
    ax_b_diff.set_title('Paired cohort difference', loc='left', fontsize=8.7, pad=7)
    ax_b_diff.set_xlabel('Difference (percentage points)', fontsize=8.5, labelpad=3)
    ax_b_diff.spines['left'].set_visible(False)
    fig.text(.60, .055, 'Thick: bounds. Thin: outer 95% interval.', fontsize=8, color='#444444')
    output_dir.mkdir(parents=True, exist_ok=True)
    stem = output_dir / 'newwave_access_figure1'
    fig.savefig(stem.with_suffix('.png'), dpi=400)
    fig.savefig(stem.with_suffix('.pdf'), metadata={'Title': 'Figure 1 Current citation access and unresolved-content bounds', 'Author': 'Community Notes source audit'})
    plt.close(fig)
    caption = (f'Figure 1. Current citation access and uncertainty in the same-post target population. '
               f'(A) Machine census of {n:,} pairs: filled diamonds show any cited URL being machine-open; '
               'open circles show the expected open probability for one uniformly chosen distinct citation within each note. '
               f'(B) Stratified AI-assisted browser-profile classifications of {browser["sampled_pairs"]:,} pairs. Group segments show '
               'weighted lower and upper estimates when unresolved content is respectively unavailable or available. '
               f'The paired difference has conservative unresolved-content bounds of {lower:+.1f} to {upper:+.1f} percentage points '
               f'(thick segment), with a Bonferroni 95% outer design interval of {outer[0]:+.1f} to {outer[1]:+.1f} points '
               '(thin line). The thick segment is not a confidence interval. Bounds are conservative when the same unknown '
               'URL occurs in both notes. Intervals condition on AI classifications and exclude annotation error. '
               'Browser-profile access may depend on existing '
               'cookies and does not establish claim support. Neither panel estimates a causal authorship effect.')
    (output_dir / 'newwave_access_figure1_caption.txt').write_text(caption + '\n', encoding='utf-8')
    metadata = {'machine_aggregate_sha256': sha(machine_path), 'browser_aggregate_sha256': sha(browser_path),
                'utility_sha256': sha(Path(__file__)), 'width_inches': 6.5, 'height_inches': 3.72, 'png_dpi': 400,
                'font': 'Old Standard TT', 'paired_conservative_bounds_percentage_points': [lower, upper],
                'bounds_interpretation': 'Conservative primary bounds; shared-URL consistency is a separate sensitivity analysis.',
                'outer_95_design_interval_percentage_points': outer, 'caption': caption,
                'outputs_sha256': {suffix: sha(stem.with_suffix(suffix)) for suffix in ['.pdf', '.png']}}
    (output_dir / 'newwave_access_figure1_manifest.json').write_text(json.dumps(metadata, indent=2) + '\n', encoding='utf-8')
    return stem


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--machine', type=Path, default=ROOT / 'results' / 'newwave_machine_aggregate.json')
    parser.add_argument('--browser', type=Path, default=ROOT / 'results' / 'newwave_browser_aggregate_with_recode.json')
    parser.add_argument('--output-dir', type=Path, default=ROOT / 'output' / 'figures')
    parser.add_argument('--font-dir', type=Path, default=FONTS)
    args = parser.parse_args()
    stem = make_figure(args.machine, args.browser, args.output_dir, args.font_dir)
    print(f'Wrote {stem}.pdf and .png from aggregate data only.')


if __name__ == '__main__':
    main()
