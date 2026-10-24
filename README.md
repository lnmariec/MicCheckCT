# MicCheckCT

A free website listing live music, open mics and karaoke across Connecticut.

## Folders

- `site/`: the website.
- `scripts/`: the calendar feed importer and helper scripts.
- `db/`: the database definition (matches Supabase).
- `design/`: the approved homepage design.
- `BUILD_BRIEF.md`: the plan and every decision so far.

## Keys

Keys live in a local `.env` file, which is never uploaded. Copy `.env.example` to `.env` and fill it in. Scheduled scripts read their keys from GitHub Actions secrets.
