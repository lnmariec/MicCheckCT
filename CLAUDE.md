# MicCheckCT

A free website listing live music, open mics and karaoke across Connecticut. Read `BUILD_BRIEF.md` before doing anything: it holds every decision so far, the database layout, the 7 calendar feeds and the build order.

## Working with Ellen

- Ellen is new to coding. Explain each technical term in plain words the first time it comes up, and say what a step will do before doing it.
- Work one build-order step at a time. Show the result, confirm it works, then move on.
- For anything Ellen must do herself (creating accounts, copying keys, clicking in Supabase, GitHub or Cloudflare), give numbered click-by-click steps and wait for her to report back.
- Ellen prefers direct, economical writing and never uses em dashes. Follow that in replies and in all site copy.

## Ground rules

- The database already exists in Supabase and is loaded. Never drop or recreate tables. Change the database only with small, reviewed SQL, and keep `db/miccheckct_schema.sql` matching what's in Supabase.
- Never put the Supabase service_role key in website code, and never commit any key or password. Keys live in a local `.env` file (listed in `.gitignore`) and in GitHub Actions secrets.
- The website uses only the public anon key. It reads the `upcoming_listings` view for listings, plus the public `towns` and `recurring_events` tables (for distance and how often a regular night runs).
- The website gets the public key from `site/config.js`, written by `scripts/make_config.py` and never committed.
- Stay within free tiers: Supabase, Cloudflare Pages, GitHub (public repo) and GitHub Actions.
- Facebook and other people's listing sites (Shoreline Live Music, Karaoverse, Wailing City, Bandsintown) are never scraped.

## Files

- `BUILD_BRIEF.md`: the plan.
- `db/miccheckct_schema.sql`: database definition, v5 (matches Supabase).
- `db/towns.sql`: the towns table and its 182 rows (already run in Supabase).
- `design/homepage-design.dc.html`: the approved homepage design, from a design tool. Use it for layout, colors, fonts and behavior; its data is sample data.
