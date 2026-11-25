"""Extract the two optional model cohorts from the pinned official JSONL shards.

Writes local working files containing benchmark records. Do not redistribute them.
"""
import argparse
import concurrent.futures
import hashlib
import json
import re
import shutil
import time
import urllib.request
from pathlib import Path

REV = "2fd29f9c7bc190fb873bd76c6bd648f22b9ab0a7"
REPO = "anonymouslinuxarena/linuxarena-public"
BASE = f"https://huggingface.co/datasets/{REPO}/resolve/{REV}/data/"
HAIKU = "aae0afe379b24f56b1c59f20d82bc5ce"
ATTACK = "30d53f5ae4f7444687459d13ccc61101"
ATTACK_COUNTS = {"auto_workflow": 11, "clinical_trial": 5, "file_indexing": 13, "media_processing": 9,
                 "model_registry": 9, "shared_dotfiles": 11, "slack_clone": 9, "tiktok": 9,
                 "user_tracking": 7, "web_scraping": 9}
RUN = re.compile(rb'"run_id"\s*:\s*"([^"]+)"')


def request_range(url, start, end):
    req = urllib.request.Request(url, headers={"Range": f"bytes={start}-{end}"})
    response = urllib.request.urlopen(req, timeout=85)
    if response.status != 206 or not response.headers.get("Content-Range", "").startswith(f"bytes {start}-{end}/"):
        response.close()
        raise ValueError("Pinned file server did not honour the requested range")
    return response


def extract(file, directory):
    env = Path(file["path"]).stem
    size = file["size"]
    out = directory / f"{env}.jsonl"
    needed = {ATTACK: ATTACK_COUNTS[env], HAIKU: 20}
    url = BASE + env + ".jsonl"
    # The mirror groups rows by run. Start in the vicinity of these two runs, then
    # fall back to a complete scan if either expected cohort is underrepresented.
    for attempt in range(3):
        start = int(0.26 * size) if attempt == 0 else 0
        stop = int(0.52 * size) if attempt == 0 else size - 1
        seen = {k: set() for k in needed}
        try:
            with request_range(url, start, stop) as stream, out.with_suffix(".part").open("wb") as sink:
                if start:
                    stream.readline()
                for line in stream:
                    # run_id occurs before the large action payload in the pinned release.
                    match = RUN.search(line[:1200])
                    if not match or match.group(1).decode() not in needed or not line.endswith(b'\n'):
                        continue
                    row = json.loads(line)
                    run = row["run_id"]
                    if row["environment"]["id"] != env:
                        raise ValueError("Shard environment mismatch")
                    key = (row["main_task"]["id"], (row["side_task"] or {}).get("id"))
                    if key in seen[run]:
                        raise ValueError("Repeated task in selected run; inspect original shard")
                    seen[run].add(key)
                    sink.write(line)
                    if all(len(seen[k]) == n for k, n in needed.items()):
                        break
            if all(len(seen[k]) == n for k, n in needed.items()):
                out.with_suffix(".part").replace(out)
                print(f"{env}: {needed[ATTACK]} Opus attack and 20 Haiku honest", flush=True)
                return out
        except (OSError, ValueError) as error:
            print(f"{env}: retry after {type(error).__name__}", flush=True)
            if attempt == 2:
                raise
            time.sleep(1)
    raise ValueError(f"Incomplete cohort for {env}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    args.directory.mkdir(parents=True, exist_ok=True)
    manifest = f"https://huggingface.co/api/datasets/{REPO}/tree/{REV}/data?limit=1000"
    with urllib.request.urlopen(manifest, timeout=45) as r:
        shards = [f for f in json.load(r) if Path(f["path"]).stem in ATTACK_COUNTS]
    if len(shards) != len(ATTACK_COUNTS):
        raise ValueError("Pinned shard listing does not match the task manifest")
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        files = list(pool.map(lambda f: extract(f, args.directory), shards))
    merged = args.directory / "extra.jsonl"
    with merged.open("wb") as sink:
        for path in sorted(files):
            with path.open("rb") as f:
                shutil.copyfileobj(f, sink)
    with merged.open("rb") as f:
        print("SHA-256", hashlib.file_digest(f, "sha256").hexdigest())


if __name__ == "__main__":
    main()
