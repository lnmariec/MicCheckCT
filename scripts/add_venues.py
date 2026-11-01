"""Add venues Ellen has approved, from a CSV in db/updates/ (columns: name,
town, venue_type, notes). Skips any venue whose slug already exists, so it is
safe to run twice. Address and website can be filled in later.

  python scripts/add_venues.py db/updates/2026-11-01_feed_venues.csv --dry-run
  python scripts/add_venues.py db/updates/2026-11-01_feed_venues.csv
"""

import csv
import re
import sys
import unicodedata
from pathlib import Path

from import_feeds import Supabase, load_settings


def slugify(name):
    text = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower()
    text = text.replace("&", " and ").replace("'", "")
    return re.sub(r"[^a-z0-9]+", "-", text).strip("-")


def main():
    path, dry_run = Path(sys.argv[1]), "--dry-run" in sys.argv
    db = Supabase(*load_settings())
    towns = {t["name"] for t in db.get_all("towns?select=name")}
    slugs = {v["slug"] for v in db.get_all("venues?select=slug")}

    rows = []
    with open(path, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            slug = slugify(r["name"])
            if r["town"] not in towns:
                sys.exit(f"Town not in the towns table: {r['town']} ({r['name']}). Nothing was added.")
            if slug in slugs:
                print(f"  already there, skipped: {r['name']}")
                continue
            rows.append({"name": r["name"], "slug": slug, "town": r["town"],
                         "venue_type": r["venue_type"] or None, "notes": r["notes"] or None})
            print(f"  {'would add' if dry_run else 'add'}: {r['name']} ({r['town']}) as {slug}")

    if rows and not dry_run:
        db.request("POST", "venues", rows, prefer="return=minimal")
    print(f"{len(rows)} venues {'would be ' if dry_run else ''}added")


if __name__ == "__main__":
    main()
