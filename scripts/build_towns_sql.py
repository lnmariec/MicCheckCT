"""Build db/towns.sql: the towns table with a center point for every place
the site uses. Run once; the result is reviewed, then run in Supabase.

Sources (public domain):
  - Census 2025 Gazetteer, CT county subdivisions: all 169 CT towns
  - Census 2025 Gazetteer, CT and NY places: villages (CDPs) and Pawling, NY
  - Four villages the Census doesn't list, in EXTRA below

Usage:  python scripts/build_towns_sql.py <folder with the Gazetteer .txt files>
"""

import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "db" / "towns.sql"

# Villages used in venues.town that are Census places (CDPs or villages).
CENSUS_VILLAGES = {
    "CT": ["Baltic", "Mashantucket", "Moosup", "Mystic", "Niantic", "Northford", "Willimantic", "Winsted"],
    "NY": ["Pawling"],
}

# Villages the Census doesn't list: (name, latitude, longitude, where the point came from)
EXTRA = [
    ("Milldale", 41.565868, -72.891815, "Wikipedia (USGS GNIS)"),
    ("South Glastonbury", 41.666390, -72.604170, "Wikipedia (USGS GNIS)"),
    ("Uncasville", 41.434440, -72.109720, "Wikipedia (USGS GNIS)"),
    ("Unionville", 41.758419, -72.889217, "Census geocoder, 15 School St"),
]


def read_gazetteer(path):
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f, delimiter="|"))


def strip_suffix(name, suffixes):
    for suffix in suffixes:
        if name.endswith(" " + suffix):
            return name[: -len(suffix) - 1]
    return name


def main():
    folder = Path(sys.argv[1])
    rows = []  # (name, state, kind, lat, lon)

    for r in read_gazetteer(folder / "2025_gaz_cousubs_09.txt"):
        if r["NAME"].endswith(" town"):
            rows.append((strip_suffix(r["NAME"], ["town"]), "CT", "town",
                         float(r["INTPTLAT"]), float(r["INTPTLONG"])))

    for state, wanted in CENSUS_VILLAGES.items():
        fips = {"CT": "09", "NY": "36"}[state]
        places = {strip_suffix(r["NAME"], ["CDP", "village"]): r
                  for r in read_gazetteer(folder / f"2025_gaz_place_{fips}.txt")
                  if r["NAME"].endswith((" CDP", " village"))}
        for name in wanted:
            r = places[name]
            rows.append((name, state, "village", float(r["INTPTLAT"]), float(r["INTPTLONG"])))

    for name, lat, lon, _ in EXTRA:
        rows.append((name, "CT", "village", lat, lon))

    towns = sum(1 for r in rows if r[2] == "town")
    assert towns == 169, f"expected 169 CT towns, got {towns}"
    assert len({(r[0], r[1]) for r in rows}) == len(rows), "duplicate name"
    rows.sort(key=lambda r: (r[1], r[0]))

    values = ",\n".join(
        "  ('{}', '{}', '{}', {:.6f}, {:.6f})".format(name.replace("'", "''"), state, kind, lat, lon)
        for name, state, kind, lat, lon in rows)
    extra_notes = "\n".join(f"--   {name}: {source}" for name, _, _, source in EXTRA)

    OUT.write_text(f"""-- =====================================================================
-- MicCheckCT: towns table (schema v5)
-- Adds a center point for every place a visitor can pick, so the site can
-- measure distance between towns. Creates one new table; changes nothing else.
-- Run once in Supabase: Dashboard > SQL Editor > New query > paste > Run
--
-- {len(rows)} rows: all 169 CT towns, {len(rows) - 170} CT villages used in venues.town, Pawling NY.
-- Points are Census 2025 Gazetteer internal points, except:
{extra_notes}
-- Built by scripts/build_towns_sql.py
-- =====================================================================

begin;

create table towns (
  name       text not null,               -- matches venues.town
  state      text not null default 'CT',
  kind       text not null check (kind in ('town', 'village')),  -- village = part of a town
  latitude   numeric(9,6) not null,
  longitude  numeric(9,6) not null,
  primary key (name, state)
);

alter table towns enable row level security;

create policy "public can read towns"
  on towns for select to anon, authenticated using (true);

grant select on towns to anon, authenticated;

insert into towns (name, state, kind, latitude, longitude) values
{values};

commit;
""", encoding="utf-8")
    print(f"Wrote {OUT.relative_to(ROOT)}: {len(rows)} rows ({towns} towns, {len(rows) - towns} villages)")


if __name__ == "__main__":
    main()
