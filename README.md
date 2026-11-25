# One cutoff, ten review workloads

Does a 1% review cutoff for an AI-control monitor keep the review queue within budget when the agent moves to a new kind of work? This repository holds the code, derived tables and offline checks behind a three-page research note on that question, using public LinuxArena data.

Doug Christopher, 25 November 2026. The note is [LinuxArena_research_note.pdf](LinuxArena_research_note.pdf).

## Main result

The data are GPT-5 Nano action-monitor scores for 200 honest Claude Opus tasks, 20 in each of ten LinuxArena environments, 12,494 scored actions in all. Each environment took its cutoff from the other nine, and all ten splits chose 7.5.

- With ties at the cutoff broken at random so that the source data spends exactly 1%, the expected false-alert rate across all ten held-out environments was 10.8 per 1,000 actions. File Indexing got 21.2 per 1,000, more than twice its budget.
- Flagging scores above 7.5 gave 105 alerts. Flagging 7.5 and above gave 199, because 94 actions sit exactly at 7.5.
- Ten tasks produced 61 of the 105 alerts. Shuffling whole tasks between environments gives exploratory p-values of about 0.08 to 0.11, against 1.79e-8 when actions are treated as independent.
- In simulation, a hierarchical estimator with a wider choice of cutoffs moved closer to budget as local tasks were added. On the recorded splits, local and hierarchical estimates beat pooling on average but got worse when given the wider rule.

## Quick check

Needs Python 3.9 or later and nothing else. From the repository root:

    python verify_offline.py

It rebuilds the ten held-out environment rows from the per-task score table and checks them against the original results. Expected output:

    Threshold scores >7.5: 105 out of 12494
    Ties at 7.5: 94  | environments exceeding 1%: 4
    Whole-task permutation p: 0.0763
    Attack coverage bounds: 59/92 to 84/92
    All ten environment rows agree with the original release.

## Full analysis

These need NumPy, pandas and SciPy. The figures also need matplotlib.

    python checks/indep_check.py tables/honest_tasks.csv
    python checks/oracle_floor.py analysis/design_simulation.py tables/honest_tasks.csv
    python analysis/levels_design.py

The reported extension is analysis/levels_design.py, and the two-stage predecessor is analysis/design_simulation.py. Tables prefixed levels_ belong to the extension. ADDENDUM.md explains the extension, and METHODS.md describes the predecessor and the dataset. The files in checks/ are cross-checks written separately during review.

Run the extension in a copy if you want to keep the reference CSVs. Random seeds are fixed, but numerical optimisers near a zero-variance boundary can behave differently across dependency versions. A full rerun from the supplied task histograms reproduced the fit JSON and all three levels_ CSVs byte for byte under both Python 3.12.14 (NumPy 2.3.5, SciPy 1.17.0, pandas 2.2.3) and Python 3.13.18 (NumPy 2.5.3, SciPy 1.18.1, pandas 3.0.5). It takes about three minutes. Use levels_observed_summary.csv for mean error, interval coverage and interval score. An absolute error computed after averaging over random tie decisions can be smaller than the average error of actual review queues.

To rebuild the note from the tables (needs reportlab, plus matplotlib or a folder of DejaVu fonts named in NOTE_FONT_DIR):

    python note/build_note.py . LinuxArena_research_note.pdf

## Layout

- LinuxArena_research_note.pdf: the research note.
- verify_offline.py: the standard-library check above.
- tables/: per-task score histograms and analysis outputs. tables/honest_tasks.csv is the 200-row score table.
- analysis/: the extension, its predecessor, task-level checks and plotting.
- checks/: separately written cross-checks.
- figures/: figures produced by analysis/plot_levels.py.
- note/: the script that draws the note.
- original/: the archived pilot, with the raw-data extraction, analysis plan and original results. Its README keeps its original wording.

## Rebuilding from raw data

The offline checks start from derived score histograms. Rebuilding those from the raw benchmark trajectories is a separate step, described in original/README.md, which covers the pinned dataset revision, the file checksum and the run identifiers. Raw evaluation files (sample.jsonl and the extra/ folder) are excluded by .gitignore and should stay on your machine.

## Data and attribution

The data come from the LinuxArena public mirror, revision 2fd29f9c7bc190fb873bd76c6bd648f22b9ab0a7, which labels its trajectories CC BY 4.0. The [Control Leaderboard data notice](https://control-leaderboard.redwoodresearch.org/data) also limits use to evaluation and excludes model training. This repository contains only derived counts and summaries, not raw trajectories. If you reuse the tables, please keep the attribution to the LinuxArena authors.

- [LinuxArena paper](https://arxiv.org/abs/2604.15384)
- [Pinned dataset](https://huggingface.co/datasets/anonymouslinuxarena/linuxarena-public/tree/2fd29f9c7bc190fb873bd76c6bd648f22b9ab0a7)
- [Published run identifiers](https://github.com/redwoodresearch/linuxarena-paper/blob/main/src/results/public_run_ids.json)
- [Shortcut Sensitivity in Agent-Safety Evaluations](https://arxiv.org/abs/2610.22243), whose audit documents the deduplication, input checksum and monitor parsing

## Related work

- Olmo, Zhang and Tracy (2026), [Simulated Control Evals](https://arxiv.org/abs/2610.31593). Simulated control evaluations explain most of the variation in safety and monitor scores between LinuxArena environments.
- [ControlArena issue 938](https://github.com/UKGovernmentBEIS/control-arena/issues/938). On BashArena logs, tied trajectory scores left a nominal 1% audit budget unspent for six of ten monitors. One suggested fix audits a random share of ties.

This study differs in working at the action level, holding out whole environments and measuring the review workload a fixed cutoff creates in each one.

## AI use

ChatGPT and Claude assisted with research design, analysis code, cross-checks and drafting. Agreement between the two systems is a reproducibility check on this dataset, not independent evidence.

## Licence and citation

The code is released under the MIT licence (see LICENSE). The derived tables remain subject to the dataset's CC BY 4.0 terms and data notice. Citation details are in CITATION.cff.
