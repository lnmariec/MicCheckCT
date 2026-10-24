"""Check that the Supabase keys in .env work. Reads only; never writes.

Run from the project folder:  python scripts/check_connection.py
"""

import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ENV_FILE = Path(__file__).resolve().parent.parent / ".env"


def load_env():
    values = {}
    for line in ENV_FILE.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def get(url, key, path, count=False):
    """GET a Supabase REST path. Returns (status, rows, content_range)."""
    headers = {"apikey": key, "Accept": "application/json"}
    if key.startswith("eyJ"):  # older keys also go in the Authorization header
        headers["Authorization"] = f"Bearer {key}"
    if count:
        headers["Prefer"] = "count=exact"
    request = urllib.request.Request(f"{url}/rest/v1/{path}", headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.status, json.load(response), response.headers.get("Content-Range")
    except urllib.error.HTTPError as error:
        return error.code, None, None


def main():
    env = load_env()
    url = env.get("SUPABASE_URL", "").rstrip("/")
    anon = env.get("SUPABASE_ANON_KEY", "")
    secret = env.get("SUPABASE_SERVICE_ROLE_KEY", "")

    missing = [name for name, value in
               [("SUPABASE_URL", url), ("SUPABASE_ANON_KEY", anon), ("SUPABASE_SERVICE_ROLE_KEY", secret)]
               if not value]
    if missing:
        print("Missing in .env:", ", ".join(missing))
        return 1
    if anon == secret:
        print("The two keys in .env are the same. The anon and service_role keys should differ.")
        return 1

    ok = True

    # 1. Public key reads upcoming listings.
    status, rows, _ = get(url, anon, "upcoming_listings?select=start_at,time_known,title,venue_name,town&order=start_at&limit=5")
    if status == 200 and rows:
        print(f"PASS  Public key reads upcoming_listings. First {len(rows)}:")
        for row in rows:
            # start_at is in UTC; show the time only when it is known
            when = row["start_at"][:16].replace("T", " ") + " UTC" if row["time_known"] else row["start_at"][:10] + " Time TBA"
            print(f"        {when}  {row['title']}  ({row['venue_name']}, {row['town']})")
    else:
        print(f"FAIL  Public key could not read upcoming_listings (status {status}).")
        ok = False

    # 2. Public key must not see the private sources table.
    status, rows, _ = get(url, anon, "sources?select=id&limit=1")
    if status != 200 or rows == []:
        print("PASS  Public key cannot see the private sources table.")
    else:
        print("FAIL  Public key can read sources. It should be private.")
        ok = False

    # 3. Secret key sees all sources.
    status, rows, content_range = get(url, secret, "sources?select=id&limit=1", count=True)
    total = content_range.split("/")[-1] if content_range else "?"
    if status in (200, 206):  # 206 is normal when a count is requested
        print(f"PASS  Secret key reads sources: {total} rows (expected 35).")
    else:
        print(f"FAIL  Secret key could not read sources (status {status}).")
        ok = False

    print("\nAll checks passed." if ok else "\nSome checks failed.")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
