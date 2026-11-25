# Addendum, 22 November 2026: a randomised threshold across 7.0, 7.5 and 8.0

This addendum extends the design study on page 3 of the note. The original files are unchanged. New code is in `analysis/levels_design.py` and `analysis/plot_levels.py`, new results are the `tables/levels_*` files, and the figure is `figures/levels_design_curve.png`. Everything here is exploratory and was added after the November 19 and 21 results.

## Why the rule needed widening

In the original design study, every method always flagged scores of 8.0 and above and chose only what share of the 7.5 ties to flag. Under that rule, an environment can meet the target in expectation only if 1% lies between its strict and inclusive rates. Four of the ten recorded environments exceed 1% even with no ties flagged. Most of the alert mass sits on three neighbouring levels: across all 12,494 actions there are 78 scores of 7.0, 94 of 7.5, 83 of 8.0 and only 22 above 8.0.

## What changed

**Model.** A chain of four conditional stages replaces the two-stage model: scores of at least 7.0 among all actions, at least 7.5 among those, at least 8.0 among those, and above 8.0 among those. Each stage keeps the packet's structure: a beta-distributed probability for each task, a normal environment effect on the log odds, 19-point quadrature, and the same fitting and updating code, imported unchanged from `design_simulation.py`. The third stage is the original second stage. Fitting with only the 7.5 level free reproduces the original parameters exactly.

**Rule.** Always flag scores above 8.0. Then fill the 1% budget downward through 8.0, 7.5 and 7.0, flagging a random share of the level where the predicted budget runs out and nothing below it. With a single level this is exactly the original tie rule, which was checked numerically on 100,000 random inputs.

**Comparison.** The old tie-only rule is evaluated in the same simulated worlds, with the same calibration tasks, test tasks and audit lottery, so old-versus-new comparisons are paired. A perfect-knowledge method that knows each new environment's true rates shows the floor each rule allows. The scenarios, designs, error measure and detection tests are the packet's own. A sensitivity run adds the 6.5 level.

**Recorded tasks.** Each environment is left out of the fit in turn. The method calibrates on 5 or 10 of its tasks and is scored on the rest, over 16 overlapping partitions. Recorded budget error is the absolute deviation of the lottery-averaged alert rate from target. An actual random tie draw introduces additional variability. Coverage uses each method's 80% range for alerts under its own rule. A hindsight method that sets the rule from the test tasks' own counts shows what the rule could achieve if the batch were known in advance.

## Fitted stages (7.0 to 8.0)

| Stage | Log-odds centre | Environment SD | Task concentration |
|---|---:|---:|---:|
| At least 7.0, of all actions | -4.16 | 0.58 | 20.8 |
| At least 7.5, given at least 7.0 | 0.93 | 0.00 | 13,184 |
| At least 8.0, given at least 7.5 | 0.10 | 0.00 | 36.0 |
| Above 8.0, given at least 8.0 | -1.38 | 0.27 | 3,280 |

Environments differ mainly in how often actions reach 7.0 at all. The split between 7.0, 7.5, 8.0 and above shows little or no detectable environment variation, but ten environments cannot rule it out.

## Design study results (fitted scenario)

Mean distance from ten alerts per 1,000 under the true simulated rates, in 500 studies of ten new environments. "Old" is the tie-only rule; "new" is the randomised threshold.

| Local tasks | Pooled | Local only (old / new) | Hierarchical (old / new) | Perfect knowledge (old / new) |
|---:|---:|---:|---:|---:|
| 1 | 4.47 | 4.61 / 6.78 | 4.20 / 4.19 | 2.05 / 0.63 |
| 5 | 4.47 | 3.97 / 4.86 | 3.64 / 3.49 | 2.05 / 0.63 |
| 10 | 4.47 | 3.66 / 4.03 | 3.34 / 3.01 | 2.05 / 0.63 |
| 20 | 4.47 | 3.32 / 3.25 | 3.04 / 2.49 | 2.05 / 0.63 |
| 40 | 4.47 | 3.04 / 2.60 | 2.78 / 2.03 | 2.05 / 0.63 |
| 160 | 4.47 | 2.58 / 1.66 | 2.50 / 1.47 | 2.05 / 0.63 |

- **The wider rule reduced the floor in the fitted simulation.** The floor falls from 2.05 to 0.63 per 1,000. With perfect knowledge, no sampled environment had material overload under the wider rule. What remains is unused budget in very quiet environments.
- **Five or ten local tasks use little of the new room.** The hierarchical method improves by 0.15 per 1,000 at 5 tasks and 0.33 at 10, against 0.75 at 40 and 1.03 at 160. Local-only estimates get worse under the wider rule until about 20 tasks, because more freedom means more ways to be wrong.
- **Overload barely moves at small samples.** 27% of new environments run more than 20% over budget under the pooled rule. With the hierarchical method under the new rule, that is 26% at 5 tasks, 24% at 10, 16% at 40 and 7% at 160.
- **The gain depends on how different environments really are.** With stronger environment differences, the hierarchical method at 10 tasks reaches 4.51 under the new rule against 6.62 under the old one, with the pooled rule at 8.82. With no environment differences, pooled and hierarchical make no error and local-only reaches 4.66 under the new rule.
- **Still hard to demonstrate with ten environments.** The hierarchical method beats pooling in 5.0% (5/15), 6.2% (10/10) and 9.8% (10/100) of studies by the sign test, and in 8.8%, 10.4% and 25.4% by the sign-flip test. Its new-rule version beats its old-rule version in 0.0%, 0.4% and 5.2%.
- **Adding 6.5 lowers the floor to 0.16** and shows the same pattern. Because the first stage moves, the simulated worlds differ slightly between the two level sets, so compare rules within a level set rather than across sets.

## Recorded tasks (7.0 to 8.0)

| | 5 local tasks | 10 local tasks |
|---|---:|---:|
| Hindsight floor, old rule / new rule | 4.58 / 1.72 | 5.11 / 2.12 |
| Pooled | 8.54 | 9.01 |
| Local only, old / new | 6.91 / 7.46 | 7.07 / 7.83 |
| Hierarchical, old / new | 7.68 / 8.14 | 7.98 / 8.59 |
| 80% range coverage, pooled / local / hierarchical (new rule) | 64% / 63% / 64% | 69% / 74% / 73% |
| Interval score, pooled / local / hierarchical (new rule) | 33.9 / 54.8 / 43.0 | 27.6 / 31.7 / 31.9 |

- With the batch known in advance, the wider rule could hit the budget on most recorded batches.
- Both local estimators had smaller average error than pooling under the wider rule. Each had still smaller average error under its own narrow rule. These comparisons answer different questions.
- File Indexing and Shared Dotfiles produce errors of roughly 12 to 23 per 1,000 under every method, because a few tasks carry most of their alerts and a small calibration sample rarely contains them.
- Every method's 80% ranges still cover too little, and the pooled forecast still has the best interval score. Undercoverage is a reason for caution. It does not identify the cause or establish the direction of bias in the simulated gains.
- Partitions overlap and test batches are 10 to 15 tasks, so these numbers are descriptive rather than tests.

## What it means for the note

The wider rule reduces the minimum possible error in the fitted simulation. At five and ten local tasks the simulated hierarchical estimate improves on pooling. In the recorded splits both local estimates have lower average error than pooling, while widening the rule increases each local method’s average error. A practitioner has no externally validated task count at which to switch. The calibration and test partitions reuse the same 200 tasks. A fixed alert budget also leaves unanswered how much useful detection is retained.


## Limits

- The stages are treated as independent given the environment: task probabilities and environment effects are drawn separately for each stage.
- Environment spread is estimated from ten environments; two stage SDs sit at the zero boundary.
- As in the original study, simulated methods receive the true source parameters, which is optimistic.
- The rule targets 1% on average. It does not limit the chance of exceeding the budget in a given batch.
- Recorded-task partitions reuse tasks and assume the number of actions in each future task is known.

## Reproduce

From the extracted folder, with NumPy, pandas and SciPy:

    python analysis/levels_design.py
    python analysis/plot_levels.py

The first takes about two minutes and writes the `tables/levels_*` files. The second needs matplotlib and writes the original extension figures. The final PDF plots the same fitted-scenario data. Reference run: Python 3.13.18, NumPy 2.5.3, SciPy 1.18.1, pandas 3.0.5 and matplotlib 3.11.2. On those versions the packet's original scripts also reproduced their shipped tables exactly.
