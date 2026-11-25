"""Extended design study: a randomised threshold over the 7.0, 7.5 and 8.0 score levels.

The packet's design_simulation.py lets methods choose only the share of 7.5 ties to flag and always
flags 8.0 and above. Here the model is extended to a chain of conditional stages (score >= 7.0 out of
all actions, >= 7.5 out of >= 7.0, >= 8.0 out of >= 7.5, > 8.0 out of >= 8.0), each with the packet's
beta-binomial task variation and normal environment effect on log odds. The decision rule always flags
scores above the top level and fills the 1% budget downwards, flagging a random share of the level
where the budget runs out. The old tie-only rule is evaluated in the same simulated worlds for a paired
comparison. A sensitivity run adds the 6.5 level. Estimation, posterior updating and the detection
tests are imported unchanged from design_simulation.py. See ADDENDUM.md for assumptions and limits.

Run from the extracted packet:  python analysis/levels_design.py
"""
import importlib.util
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import brentq
from scipy.special import expit

HERE = Path(__file__).resolve().parent
TAB = HERE.parent / "tables"
_spec = importlib.util.spec_from_file_location("design_simulation", HERE / "design_simulation.py")
ds = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ds)

SEED = 20261122
BUDGET = 0.01
LEVEL_SETS = {"7.0-8.0": (14, 15, 16), "6.5-8.0": (13, 14, 15, 16)}   # histogram bins; bin i is score i/2
BIN_7P5 = 15
DESIGNS = [(1, 10), (2, 10), (5, 15), (10, 10), (20, 10), (40, 10), (80, 10), (160, 10), (10, 100)]
METHODS = ("pooled", "local", "hierarchical", "oracle")
RULES = ("tie_only", "levels")


# ---------------------------------------------------------------- data and fitting
def stage_counts(df, levels):
    """Per-task trials and successes for each stage. Stage j counts scores >= thr[j] among those >= thr[j-1]."""
    bins = df[[f"s{i:02}" for i in range(21)]].to_numpy()
    thr = list(levels) + [levels[-1] + 1]
    ge = [bins[:, t:].sum(1) for t in thr]
    return [df.n.to_numpy()] + ge[:-1], ge


def fit_stages(df, levels):
    trials, succ = stage_counts(df, levels)
    env = df.environment.to_numpy()
    names = sorted(df.environment.unique())
    return np.array([ds.fit([tr[env == e] for e in names], [sc[env == e] for e in names])
                     for tr, sc in zip(trials, succ)])


def population_means(pars):
    return np.array([ds.W @ ds.grid(p)[0] for p in pars])


# ---------------------------------------------------------------- decision rules
def level_rates(stage_p):
    """Stage probabilities (..., S) -> rate always flagged (above the top level) and level masses, top level first."""
    cum = np.cumprod(stage_p, axis=-1)
    return cum[..., -1], (cum[..., :-1] - cum[..., 1:])[..., ::-1]


def fill(always, masses):
    """Fill the budget from the top level down. A level with no predicted mass is passed while budget remains;
    the level where the budget runs out is flagged at random with the remaining share; lower levels get zero."""
    always = np.asarray(always, float)
    masses = np.asarray(masses, float)
    left = BUDGET - always
    active = left > 0
    out = np.zeros(masses.shape)
    for j in range(masses.shape[-1]):
        m = masses[..., j]
        f = np.where(m > 0, np.clip(left / np.where(m > 0, m, 1.0), 0, 1), 1.0)
        f = np.where(active, f, 0.0)
        out[..., j] = f
        left = left - f * m
        active = active & (f >= 1) & (left > 0)
    return out


def policy(always, masses, rule, levels):
    """Flag fractions per level (top level first). tie_only: all of 8.0 and above, a share of 7.5, nothing lower."""
    if rule == "levels":
        return fill(always, masses)
    top_down = list(levels)[::-1]
    i75 = top_down.index(BIN_7P5)
    out = np.zeros(masses.shape)
    out[..., :i75] = 1.0
    out[..., i75] = fill(always + masses[..., :i75].sum(-1), masses[..., i75:i75 + 1])[..., 0]
    return out


def shared_draw(rng, count, fractions):
    """Coupled lottery: methods flag nested random subsets of one level's actions (as in design_simulation.py)."""
    nenv, npol = fractions.shape
    order = np.argsort(fractions, axis=1)
    sq = np.take_along_axis(fractions, order, axis=1)
    remaining = count.astype(int).copy()
    prev = np.zeros(nenv)
    hits = np.zeros(nenv, int)
    out = np.empty((nenv, npol), int)
    for i in range(npol):
        prob = np.clip((sq[:, i] - prev) / np.maximum(1 - prev, 1e-15), 0, 1)
        inc = rng.binomial(remaining, prob)
        remaining -= inc
        hits += inc
        out[np.arange(nenv), order[:, i]] = hits
        prev = sq[:, i]
    return out


# ---------------------------------------------------------------- design simulation
def method_stage_p(method, gen, T, S, m, p_true):
    if method == "pooled":
        return np.broadcast_to(population_means(gen), p_true.shape)
    if method == "oracle":
        return p_true
    if method == "hierarchical":
        return np.stack([ds.update(gen[j], T[j][:, :m], S[j][:, :m]) @ ds.grid(gen[j])[0]
                         for j in range(len(gen))], axis=-1)
    return None  # local handled from raw counts


def local_rates(T, S, m):
    n = T[0][:, :m].sum(-1).astype(float)
    cum = np.stack([s[:, :m].sum(-1) for s in S], axis=-1) / n[:, None]
    return cum[:, -1], (cum[:, :-1] - cum[:, 1:])[:, ::-1]


def simulate(df, levels, runs=500, seed=SEED):
    pars = fit_stages(df, levels)
    nst = len(pars)
    rng = np.random.default_rng(seed)
    nenv = runs * 10
    floors = np.array([.7] + [.35] * (nst - 1))
    rows = []
    for scenario in ["no_environment_effect", "fitted", "stronger_shift"]:
        gen = pars.copy()
        if scenario == "no_environment_effect":
            gen[:, 1] = 0
        if scenario == "stronger_shift":
            gen[:, 1] = np.maximum(2 * gen[:, 1], floors)
        for j in range(nst):   # keep each stage's marginal prevalence fixed, as in design_simulation.py
            marginal = ds.W @ ds.grid(pars[j])[0]
            gen[j, 0] = brentq(lambda mu: ds.W @ expit(mu + gen[j, 1] * ds.Z) - marginal, -30, 30)
        p_true = np.stack([expit(g[0] + g[1] * rng.normal(size=nenv)) for g in gen], axis=-1)
        n = rng.choice(df.n.to_numpy(), size=(nenv, 260))
        T, S = [n], []
        for j in range(nst):
            S.append(ds.simulate_counts(rng, T[j], p_true[:, j:j + 1], gen[j, 2]))
            if j < nst - 1:
                T.append(S[j])
        true_always, true_masses = level_rates(p_true)
        for m, t in DESIGNS:
            fr, names = [], []
            for rule in RULES:
                for method in METHODS:
                    if method == "local":
                        a, ms = local_rates(T, S, m)
                    else:
                        a, ms = level_rates(method_stage_p(method, gen, T, S, m, p_true))
                    fr.append(policy(a, ms, rule, levels))
                    names.append((rule, method))
            fr = np.stack(fr, axis=1)                                   # (nenv, policies, levels)
            true_rate = true_always[:, None] + (fr * true_masses[:, None, :]).sum(-1)
            ns = n[:, -t:].sum(-1)
            cum_t = np.stack([s[:, -t:].sum(-1) for s in S], axis=-1)
            lvl_counts = (cum_t[:, :-1] - cum_t[:, 1:])[:, ::-1]
            alerts = np.repeat(cum_t[:, -1:], fr.shape[1], axis=1)
            for k in range(fr.shape[2]):
                alerts = alerts + shared_draw(rng, lvl_counts[:, k], fr[:, :, k])
            per1000 = 1000 * true_rate
            err_true = np.abs(per1000 - 10)
            err_test = np.abs(1000 * alerts / ns[:, None] - 10)
            idx = {nm: i for i, nm in enumerate(names)}
            for (rule, method), i in idx.items():
                rec = dict(levels="-".join(f"{b / 2:.1f}" for b in (levels[0], levels[-1])), scenario=scenario,
                           calibration_tasks=m, test_tasks=t, rule=rule, method=method,
                           true_budget_mae=err_true[:, i].mean(),
                           true_over=np.maximum(per1000[:, i] - 10, 0).mean(),
                           true_under=np.maximum(10 - per1000[:, i], 0).mean(),
                           share_over_by_20pct=(per1000[:, i] > 12).mean(),
                           test_budget_mae=err_test[:, i].mean(), studies=runs)
                base = idx[(rule, "pooled")]
                if method in ("local", "hierarchical"):
                    d = err_test[:, base] - err_test[:, i]
                    rec["detect_better_than_pooled"] = ds.exact_sign(d)
                    rec["detect_mean_better_than_pooled"] = ds.mean_signflip(d)
                    rec["detect_worse_than_pooled"] = ds.exact_sign(-d)
                if rule == "levels" and method != "oracle":
                    rec["detect_better_than_tie_only_same_method"] = ds.exact_sign(
                        err_test[:, idx[("tie_only", method)]] - err_test[:, i])
                rows.append(rec)
    return pars, pd.DataFrame(rows)


# ---------------------------------------------------------------- recorded-task check
def observed_check(df, levels, partitions=16, reps=400, seed=SEED + 1):
    """Leave each environment out of the fit; calibrate on 5 or 10 of its tasks; score the rest.
    Budget error is the absolute deviation of the lottery-averaged rate on the recorded test tasks.
    Coverage uses each method's 80% predictive range for alerts under its own rule, with one shared lottery."""
    rng = np.random.default_rng(seed)
    trials_all, succ_all = stage_counts(df, levels)
    out = []
    for env in sorted(df.environment.unique()):
        mask = (df.environment == env).to_numpy()
        pars = fit_stages(df.loc[~mask], levels)
        grids = [ds.grid(p)[0] for p in pars]
        T_env = [tr[mask] for tr in trials_all]
        S_env = [sc[mask] for sc in succ_all]
        for repeat in range(partitions):
            perm = rng.permutation(mask.sum())
            for m in (5, 10):
                tr_i, te_i = perm[:m], perm[m:]
                Tm = [x[tr_i][None] for x in T_env]
                Sm = [x[tr_i][None] for x in S_env]
                n_te = T_env[0][te_i]
                cum_te = np.array([s[te_i].sum() for s in S_env])
                lvl_te = (cum_te[:-1] - cum_te[1:])[::-1]
                weights = [ds.update(pars[j], Tm[j], Sm[j])[0] for j in range(len(pars))]
                stage = {"pooled": population_means(pars),
                         "hierarchical": np.array([w @ g for w, g in zip(weights, grids)])}
                u_levels = [rng.random(c) for c in lvl_te]          # shared audit lottery on recorded actions
                for rule in RULES:
                    for method in ("pooled", "local", "hierarchical", "hindsight"):
                        if method == "local":
                            a, ms = local_rates(Tm, Sm, m)
                            a, ms = a[0], ms[0]
                        elif method == "hindsight":                 # uses the test tasks' own counts
                            a, ms = cum_te[-1] / n_te.sum(), lvl_te / n_te.sum()
                        else:
                            a, ms = level_rates(stage[method])
                        f = policy(np.array(a), np.array(ms)[None], rule, levels)[0]
                        expected = cum_te[-1] + (f * lvl_te).sum()
                        rec = dict(levels="-".join(f"{b / 2:.1f}" for b in (levels[0], levels[-1])),
                                   environment=env, repeat=repeat, calibration_tasks=m, rule=rule, method=method,
                                   budget_error=abs(1000 * expected / n_te.sum() - 10),
                                   over=max(1000 * expected / n_te.sum() - 10, 0))
                        if method != "hindsight":
                            observed = cum_te[-1] + sum(int((u < fk).sum()) for u, fk in zip(u_levels, f))
                            draws = predictive_draws(rng, method, pars, weights, Tm, Sm, n_te, f, levels, reps)
                            lo, hi = np.quantile(draws, [.1, .9], method="inverted_cdf")
                            rec.update(covered=int(lo <= observed <= hi), width=hi - lo,
                                       interval_score=hi - lo + 10 * (max(lo - observed, 0) + max(observed - hi, 0)))
                        out.append(rec)
    return pd.DataFrame(out)


def predictive_draws(rng, method, pars, weights, Tm, Sm, n_te, f, levels, reps):
    """Future alerts on the test tasks (lengths known) under a fixed flag policy f."""
    nst = len(pars)
    if method == "local":     # plug-in, half-count smoothing, source task dispersion (as in design_simulation.py)
        mu = [np.full((reps, 1), (Sm[j].sum() + .5) / (Tm[j].sum() + 1)) for j in range(nst)]
    else:
        ww = [ds.W] * nst if method == "pooled" else weights
        mu = []
        for j in range(nst):
            g = ds.grid(pars[j])[0]
            mu.append(g[rng.choice(len(g), reps, p=ww[j] / ww[j].sum())][:, None])
    nn = np.broadcast_to(n_te, (reps, len(n_te)))
    trials, succ = nn, []
    for j in range(nst):
        s = ds.simulate_counts(rng, trials, np.broadcast_to(mu[j], trials.shape), pars[j][2])
        succ.append(s)
        trials = s
    cum = np.stack([s.sum(-1) for s in succ], axis=-1)
    lvl = (cum[:, :-1] - cum[:, 1:])[:, ::-1]
    return cum[:, -1] + sum(rng.binomial(lvl[:, k], f[k]) for k in range(lvl.shape[1]))


# ---------------------------------------------------------------- main
def main():
    df = pd.read_csv(TAB / "honest_tasks.csv")
    fits, sims, obs = {}, [], []
    for name, levels in LEVEL_SETS.items():
        pars, sim = simulate(df, levels)
        labels = [f">= {levels[0] / 2:.1f} of all actions"] + [
            f">= {b / 2:.1f} given >= {a / 2:.1f}" for a, b in zip(levels[:-1], levels[1:])] + [
            f"> {levels[-1] / 2:.1f} given >= {levels[-1] / 2:.1f}"]
        fits[name] = {lab: dict(logit_center=float(p[0]), environment_logit_sd=float(p[1]),
                                task_concentration=float(p[2])) for lab, p in zip(labels, pars)}
        sims.append(sim)
        obs.append(observed_check(df, levels))
    (TAB / "levels_fit.json").write_text(json.dumps(fits, indent=2) + "\n")
    sim = pd.concat(sims, ignore_index=True)
    sim.to_csv(TAB / "levels_simulation.csv", index=False)
    raw = pd.concat(obs, ignore_index=True)
    raw.to_csv(TAB / "levels_observed_splits.csv", index=False)
    summ = (raw.groupby(["levels", "rule", "calibration_tasks", "method"])
            [["budget_error", "over", "covered", "width", "interval_score"]].mean().reset_index())
    summ.to_csv(TAB / "levels_observed_summary.csv", index=False)
    show = sim[(sim.scenario == "fitted") & sim.calibration_tasks.isin([5, 10]) & sim.test_tasks.isin([15, 10, 100])]
    cols = ["levels", "calibration_tasks", "test_tasks", "rule", "method", "true_budget_mae", "true_over",
            "true_under", "test_budget_mae", "detect_better_than_pooled", "detect_mean_better_than_pooled"]
    with pd.option_context("display.width", 220, "display.max_columns", 20):
        print(show[cols].round(3).to_string(index=False))
        print(summ.round(3).to_string(index=False))


if __name__ == "__main__":
    main()
