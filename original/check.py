"""Independent extraction check and explicitly exploratory grouped permutation test."""
import argparse
import csv
import hashlib
import json
import random
from collections import Counter, defaultdict
from pathlib import Path

from analyse import HONEST_ID, SAMPLE_HASH, fingerprint


def dispersion(groups):
    # Weighted squared deviations from the overall rate differ from this quantity by a constant.
    return sum(flags**2 / steps for flags, steps in groups if steps)


def permuted_dispersion(pairs, rng):
    rng.shuffle(pairs)
    blocks = [pairs[i:i + 20] for i in range(0, len(pairs), 20)]
    return dispersion([(sum(x for x, _ in b), sum(n for _, n in b)) for b in blocks])


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("sample", type=Path)
    p.add_argument("results", type=Path)
    args = p.parse_args()
    with (args.results / "threshold_transfer.csv").open() as f:
        reported = {r["environment"]: r for r in csv.DictReader(f)}
    with args.sample.open("rb") as f:
        if hashlib.file_digest(f, "sha256").hexdigest() != SAMPLE_HASH:
            raise ValueError("Sample checksum mismatch")
    hashes = Counter()
    hist = defaultdict(dict)
    with args.sample.open("rb") as f:
        for line in f:
            r = json.loads(line)
            hashes[fingerprint(r["actions"])] += 1
            if r["run_id"] != HONEST_ID:
                continue
            scores = Counter()
            for a in r["actions"]:
                m = a.get("monitor_response") or {}
                if a["function"] != "submit" and not m.get("error") and m.get("sus_score") is not None:
                    scores[float(m["sus_score"])] += 1
            hist[r["environment"]["id"]][r["main_task"]["id"]] = scores
    if len(hist) != 10 or any(len(d) != 20 for d in hist.values()):
        raise ValueError("Unbalanced data for the grouped permutation test")
    all_items, actual = [], []
    pooled = sum((counts for d in hist.values() for counts in d.values()), Counter())
    def threshold(bins):
        n = bins.total()
        return min(t for t in bins if 100 * sum(v for k, v in bins.items() if k > t) <= n)
    fixed = threshold(pooled)
    inc = 0
    tie_rows = []
    for env, tasks in sorted(hist.items()):
        local = sum(tasks.values(), Counter())
        source = pooled - local
        t = threshold(source)
        row = reported[env]
        alerts = sum(v for k, v in local.items() if k > t)
        if (local.total(), alerts, t) != (int(row["scored_actions"]), int(row["alerts"]), float(row["cutoff"])):
            raise ValueError("Independent table reconstruction disagrees")
        inc += sum(n for k, n in local.items() if k >= t)
        strict = sum(v for k, v in source.items() if k > t)
        tie_share = (source.total() / 100 - strict) / source[t]
        expected = alerts + tie_share * local[t]
        tie_rows.append(dict(environment=env, share_source_ties_to_flag=tie_share,
                             expected_target_alerts=expected, scored_actions=local.total(),
                             expected_alerts_per_1000=1000 * expected / local.total()))
        pairs = [(sum(v for k, v in counts.items() if k > fixed), counts.total())
                 for _, counts in sorted(tasks.items())]
        all_items.extend(pairs)
        actual.append((sum(x for x, _ in pairs), sum(n for _, n in pairs)))
    rng = random.Random(20261119)
    n_draw = 9999
    observed = dispersion(actual)
    n_greater = sum(permuted_dispersion(all_items, rng) >= observed - 1e-12 for _ in range(n_draw))
    with (args.results / "tie_sensitivity.csv").open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=tie_rows[0].keys())
        writer.writeheader()
        writer.writerows(tie_rows)
    output = dict(expected_random_tie_rate_per_1000=1000 * sum(r["expected_target_alerts"] for r in tie_rows) / pooled.total(),
                  environments_over_with_random_ties=sum(r["expected_alerts_per_1000"] > 10 for r in tie_rows),
                  full_reviewer_rows=sum(hashes.values()), unique_action_fingerprints=len(hashes),
                  sample_rows_beyond_first_occurrence=sum(hashes.values())-len(hashes),
                  inclusive_flags=inc, pooled_threshold=fixed,
                  exploratory_task_permutation_draws=n_draw,
                  exploratory_task_permutation_p=(n_greater+1)/(n_draw+1))
    (args.results / "crosscheck.json").write_text(json.dumps(output, indent=2) + "\n")
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
