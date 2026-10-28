"""Check that every venue's town has a row in the towns table. Reads only.

Run from the project folder:  python scripts/check_towns.py
Rerun after adding venues: a venue whose town is missing can't be placed by distance.
"""

import json
import sys
import urllib.request
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ENV_FILE = Path(__file__).resolve().parent.parent / ".env"
IGNORED = {("Unknown", "CT")}  # hidden venues waiting for a confirmed town


def load_env():
    values = {}
    for line in ENV_FILE.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def get(url, key, path):
    headers = {"apikey": key, "Accept": "application/json"}
    if key.startswith("eyJ"):  # older keys also go in the Authorization header
        headers["Authorization"] = f"Bearer {key}"
    request = urllib.request.Request(f"{url}/rest/v1/{path}", headers=headers)
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def main():
    env = load_env()
    url = env["SUPABASE_URL"].rstrip("/")

    # The public key must be able to read towns: the website depends on it.
    towns = get(url, env["SUPABASE_ANON_KEY"], "towns?select=name,state,kind&limit=1000")
    known = {(t["name"], t["state"]) for t in towns}
    kinds = {k: sum(1 for t in towns if t["kind"] == k) for k in ("town", "village")}
    print(f"Public key reads towns: {len(towns)} rows ({kinds['town']} towns, {kinds['village']} villages)")

    # The secret key sees every venue, including hidden ones.
    venues = get(url, env["SUPABASE_SERVICE_ROLE_KEY"], "venues?select=name,town,state,is_active&limit=1000")
    missing = [v for v in venues if (v["town"], v["state"]) not in known and (v["town"], v["state"]) not in IGNORED]
    ignored = [v for v in venues if (v["town"], v["state"]) in IGNORED]
    print(f"Venues checked: {len(venues)}, in {len({(v['town'], v['state']) for v in venues})} towns")
    if ignored:
        print(f"Skipped (town not confirmed yet): {', '.join(v['name'] for v in ignored)}")

    if missing:
        print("\nVenues whose town has no row in towns:")
        for v in missing:
            print(f"  {v['name']}: {v['town']}, {v['state']}{'' if v['is_active'] else ' (hidden)'}")
        return 1
    print("\nEvery venue town matches a row in towns.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
