# MicCheckCT

A free website listing live music, open mics and karaoke across Connecticut. Read `BUILD_BRIEF.md` before doing anything: it holds every decision so far, the database layout, the 7 calendar feeds and the build order.

## Working with Ellen

- Ellen is new to coding. Explain each technical term in plain words the first time it comes up, and say what a step will do before doing it.
- Work one build-order step at a time. Show the result, confirm it works, then move on.
- For anything Ellen must do herself (creating accounts, copying keys, clicking in Supabase, GitHub or Cloudflare), give numbered click-by-click steps and wait for her to report back.
- Ellen prefers direct, economical writing and never uses em dashes. Follow that in replies and in all site copy.

## Ground rules

- The database already exists in Supabase and is loaded. Never drop or recreate tables. Change the database only with small, reviewed SQL, and keep `db/miccheckct_schema.sql` matching what's in Supabase.
- Exception for adding shows by hand (lists Ellen sends, Facebook events): show Ellen the shows and any new venues first, and once she approves, add them yourself with a script using the service_role key from `.env`. Save the approved list in `db/updates/` and commit it as the record. Anything beyond adding shows and venues (table changes, edits or deletes) still goes through reviewed SQL that Ellen runs.
- Never put the Supabase service_role key in website code, and never commit any key or password. Keys live in a local `.env` file (listed in `.gitignore`) and in GitHub Actions secrets.
- The website uses only the public anon key. It reads the `upcoming_listings` view for listings (and search), plus the public `towns` and `recurring_events` tables (for distance and how often a regular night runs) and the names in `artists` and `venues` (search suggestions).
- The website gets the public key from `site/config.js`, written by `scripts/make_config.py` and never committed.
- Stay within free tiers: Supabase, Cloudflare Pages, GitHub (public repo) and GitHub Actions.
- Facebook and other people's listing sites (Shoreline Live Music, Karaoverse, Wailing City, Bandsintown) are never scraped.

## Files

- `BUILD_BRIEF.md`: the plan.
- `db/miccheckct_schema.sql`: database definition, v5 (matches Supabase).
- `db/towns.sql`: the towns table and its 182 rows (already run in Supabase).
- `scripts/import_feeds.py`: the daily feed importer (GitHub Actions, `.github/workflows/import-feeds.yml`). `--dry-run` previews. Unmatched shows are saved hidden; once their venue exists, the next run publishes them. Feed names for existing venues go in its `ALIASES`.
- `scripts/add_venues.py`: adds approved venues from a CSV in `db/updates/`.
- `design/homepage-design.dc.html`: the approved homepage design, from a design tool. Use it for layout and behavior; its data is sample data. Its colors and fonts are replaced by the brand kit below.
- Brand kit (Nov 2026, replaces the brief's "Look" section): dark page #181818, cream text #F5F1E8, light blue #42B6E8 for all colored text (links, tagline, headline highlight), buttons (with #181818 text) and heading divider lines, blue #2677B9 for Karaoke labels, amber #F2B544 for highlight backgrounds only (selected filter, Live music labels), white #FFFFFF. League Spartan headings, Montserrat body, event and venue names in Montserrat capitals; DM Serif Display appears only in the logo. Colors and fonts are tokens at the top of `site/styles.css`.
- `site/logo.svg`: the logo for the site (trimmed, background removed) from Ellen's original `design/logo-original.svg`.
