"""How much budget error is reducible at all under the simulation's decision rule?
Decision rule in the package: always flag scores > 7.5, flag a fraction q of the 7.5 ties.
An oracle that knows each environment's true rates picks the best q; its remaining error is irreducible.
Usage: python oracle_floor.py <path to design_simulation.py> <path to honest_tasks.csv>"""
import importlib.util
import sys
import numpy as np
import pandas as pd
from scipy.optimize import brentq
from scipy.special import expit

spec = importlib.util.spec_from_file_location("ds", sys.argv[1])
ds = importlib.util.module_from_spec(spec); spec.loader.exec_module(ds)
df = pd.read_csv(sys.argv[2])
pars = ds.fit_both(df)

def best_q(p0, p1):
    return np.clip((0.01 - p0 * p1) / (p0 * (1 - p1)), 0, 1)

def err(p0, p1, q):
    return np.abs(1000 * p0 * (p1 + q * (1 - p1)) - 10)

rng = np.random.default_rng(1)
for scenario in ["fitted", "stronger_shift"]:
    gen = np.array(pars).copy()
    if scenario == "stronger_shift":
        gen[:, 1] = np.maximum(2 * gen[:, 1], [.7, .35])
    for j in range(2):  # same marginal-matching step as the package
        marginal = ds.W @ ds.grid(pars[j])[0]
        gen[j, 0] = brentq(lambda mu: ds.W @ expit(mu + gen[j, 1] * ds.Z) - marginal, -30, 30)
    p0 = expit(gen[0, 0] + gen[0, 1] * rng.normal(size=200_000))
    p1 = expit(gen[1, 0] + gen[1, 1] * rng.normal(size=200_000))
    gm, _, _ = ds.grid(gen[0]); gs, _, _ = ds.grid(gen[1])
    pa, pb = ds.W @ gm, ds.W @ gs
    q0 = float(ds.cut(np.array(pa * pb), np.array(pa * (1 - pb))))
    pooled = err(p0, p1, q0).mean(); oracle = err(p0, p1, best_q(p0, p1)).mean()
    print(f"[{scenario}] pooled tie share q0={q0:.3f}  pooled error {pooled:.2f}  oracle (tie-only) error {oracle:.2f}"
          f"  -> reducible {pooled - oracle:.2f} per 1000")
    print(f"   envs over budget even flagging no ties: {100*np.mean(p0*p1 > .01):.0f}%   "
          f"under budget even flagging all ties: {100*np.mean(p0 < .01):.0f}%")

print("\nObserved environments, tie-only oracle (knows each environment's own rates):")
bins = df[[f"s{i:02}" for i in range(21)]]
rows = []
for e, g in df.groupby("environment"):
    n = g.n.sum(); strict = g.strict.sum(); tie = g.tie.sum(); s16 = bins.loc[g.index, "s16"].sum()
    best = min(max((0.01 * n - strict) / tie, 0), 1) if tie else 0.0
    rows.append(dict(env=e, per1000_gt75=1000 * strict / n, per1000_ge75=1000 * (strict + tie) / n,
                     oracle_err=abs(1000 * (strict + best * tie) / n - 10), at_8p0=int(s16), above_8p0=int(strict - s16),
                     share_of_8p0_to_hit_1pct=np.clip((0.01 * n - (strict - s16)) / s16, 0, 1) if s16 else np.nan))
r = pd.DataFrame(rows).sort_values("per1000_gt75", ascending=False)
print(r.round(2).to_string(index=False))
print(f"mean tie-only oracle error {r.oracle_err.mean():.2f} per 1000;"
      f" alerts exactly at 8.0: {r.at_8p0.sum()} of {df.strict.sum()}; above 8.0: {r.above_8p0.sum()}")
tot = bins.sum()
print("whole-data counts at 7.0 / 7.5 / 8.0 / >8.0:", int(tot.s14), int(tot.s15), int(tot.s16), int(tot[17:].sum()))
