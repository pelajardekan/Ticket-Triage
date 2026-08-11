#!/usr/bin/env python3
"""
Push the sample tickets in data/seed_tickets.json into a running API.

    python scripts/seed_api.py                       # against http://localhost:4280
    python scripts/seed_api.py --base https://<app>.azurestaticapps.net

The `expected` field in the seed file is the human-labelled answer. The script
reports how often the classifier agreed, which is a quick, demo-friendly
accuracy check you can screenshot for your presentation.
"""

import argparse
import json
import pathlib
import sys
import urllib.error
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
SEED_FILE = ROOT / "data" / "seed_tickets.json"


def post(base: str, payload: dict) -> dict:
    request = urllib.request.Request(
        f"{base.rstrip('/')}/api/tickets",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="http://localhost:4280",
                        help="Base URL of the running app (SWA CLI default is port 4280).")
    args = parser.parse_args()

    seeds = json.loads(SEED_FILE.read_text(encoding="utf-8"))
    agreed = 0

    for seed in seeds:
        expected = seed.pop("expected", "")
        try:
            created = post(args.base, seed)
        except urllib.error.HTTPError as exc:
            print(f"  FAILED  {seed['title']}: HTTP {exc.code} {exc.read().decode('utf-8', 'ignore')[:160]}")
            continue
        except urllib.error.URLError as exc:
            print(f"Cannot reach {args.base}: {exc.reason}")
            return 1

        got = created.get("suggestedCategory", "")
        match = got == expected
        agreed += int(match)
        flag = "ok  " if match else "MISS"
        print(f"  {flag}  {seed['title'][:44]:<46} expected={expected:<20} got={got:<20} "
              f"({created.get('classificationMethod')}, {created.get('classificationConfidence')})")

    total = len(seeds)
    print(f"\nAgreement with human labels: {agreed}/{total} = {agreed / total:.0%}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
