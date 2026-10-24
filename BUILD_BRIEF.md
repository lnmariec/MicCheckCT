# MicCheckCT Build Brief

Oct 13, 2026 · Ellen. Copy of the "MicCheckCT Build Brief" doc in claude.ai; if the two disagree, ask Ellen which is current.

## Purpose and scope

MicCheckCT is a free website listing live music, open mics, and karaoke across Connecticut, so locals can find what's on near them this week. Version 1 goal: a live, working site at a real domain, fed by data already in the database plus seven automatic calendar feeds.

- **Coverage:** Connecticut, plus Connecticut bands playing just over the border. Live music and karaoke; not DJ or nightlife venues.
- **Audience:** locals looking for something to do or somewhere to play, mostly on phones.
- **Owner:** Ellen. She is new to coding: explain every technical term in plain language the first time it comes up, and say what each step does before doing it.

## Where things stand

The database is designed and loaded with starting data; the homepage is designed; no website code exists yet. The catch-up update ran in Supabase on Oct 13, so the database is current.

| Piece | Status | Where it lives |
| --- | --- | --- |
| Database setup (schema v4) | In Supabase, current as v4 | `db/miccheckct_schema.sql` |
| Starting data and catch-up update | Both run in Supabase (Oct 2026) | MicCheckCT claude.ai Project |
| Homepage design | Approved: town-first layout, distance filter, remembered town | `design/homepage-design.dc.html` |
| Website | Not started | |
| Feed importer | Not started; 7 feeds ready | |
| Domain | Owned (MicCheckCT); connect at launch | Ellen's registrar |

The site already has about 1,100 listings in the next 60 days: roughly 260 dated shows plus the weekly karaoke, open mic and jam nights.

## Tech stack and cost

Everything runs on free tiers; the only cost is the domain, about $10 to $15 a year. Pricing and limits were checked on October 12, 2026.

| Tool | Job | Plan | Watch out for |
| --- | --- | --- | --- |
| Supabase | Database (Postgres) | Free | Free projects pause after 7 days with no activity; the daily importer keeps it awake |
| Cloudflare Pages | Hosts the website | Free | Chosen over Vercel (free plan bans commercial use, including donations) and Netlify (credit limits hurt daily rebuilds) |
| GitHub + GitHub Actions | Stores the code; runs the importer on a daily schedule | Free, **public repo** | Scheduled jobs switch off after 60 days with no repo activity; re-enable with one click. Keys go in GitHub's encrypted secrets, never in code |
| Python | Feed importer | Free | Use the `icalendar` library; avoid Playwright unless a site truly needs it |
| Claude Code | Builds everything | Included with Ellen's Claude plan | |

Prefer a site that reads listings from Supabase when a visitor loads the page, so new data shows up without rebuilding and redeploying the site.

## The database

The website reads one view, `upcoming_listings`; importers write to `events` and update `sources`. The full definition is `db/miccheckct_schema.sql` (v4), which matches Supabase.

| Table | Holds | Notes |
| --- | --- | --- |
| `venues` | 283 places | Includes 1 out-of-state venue (Daryl's House Club, NY). `latitude`/`longitude` exist but are empty; `is_active = false` hides a venue (8 hidden) |
| `artists` | 410 bands and performers | `is_local = false` marks touring acts. Acts from Park City Music Hall and Space Ballroom are kept in event titles only |
| `sources` | 35 data sources, private | 7 active ICS feeds; the rest are scraper candidates or hand-checked sources, with notes on each |
| `events` | 309 one-off dated shows | Unique on (`source_id`, `external_uid`): feed shows already carry their feed IDs so re-imports update rather than duplicate. `time_tba = true` when the venue posts a date but no start time |
| `event_artists` | Which bands play which events | |
| `recurring_events` | 118 weekly or monthly rules (105 active): karaoke, open mics, jams, house bands | `start_time` may be blank (time TBA); `week_of_month` 1 to 4 or -1 for last; `every_n_weeks` + `anchor_date` for every-other-week nights |
| `recurring_exceptions` | Dates a rule is skipped | |

**`upcoming_listings` view:** one-off events plus recurring rules expanded into real dates for the next 60 days, in America/New_York time. Columns: `id`, `listing_type`, `title`, `category`, `venue_id`, `venue_name`, `town`, `start_at`, `end_at`, `time_known`, `price_text`, `ticket_url`, `event_url`. `time_known` is false for time-TBA shows and rules with no start time. Handles nights that end after midnight.

**Security:** row level security is on for every table. The public (anon) key can only read published events, active venues and rules, and artists; `sources` is fully private. Importers use the secret service_role key, which bypasses these rules and must never appear in website code. Stage 2 will add one policy letting the public submit events as `pending`.

## Website v1 requirements

Build the homepage as `design/homepage-design.dc.html` shows: town first, filtered by distance, remembering the visitor's town. (That file comes from a design tool; it is HTML plus a small script, and its sample data is hard-coded. Use it for layout, colors, fonts and behavior, not as code to copy.)

1. **Town and distance.** Visitors pick their town and a distance (5, 10, 15, 25 or 50 miles). Default: New Haven, 15 miles.
2. **Remember the town** in the visitor's own browser (local storage) and preselect it on the next visit. No accounts, no personal data sent anywhere. Show the line "We'll remember your town on this device."
3. **Grouped by town, nearest first.** Each town heading shows "Your town" or "N mi away" and a listing count. Within a town, listings run by date, then time.
4. **Type filter:** All, Live music, Open mic, Karaoke. Works together with distance.
5. **Listing row:** day, time (or "Time TBA" in a dimmer color when `time_known` is false), act or event name, venue, an optional short note, and a type label.
6. **Summary line,** for example "11 listings in 4 towns within 15 miles of New Haven"; a friendly empty state suggesting a wider distance.
7. **Side panel** (stacks under the listings on phones): a "Playing out?" box whose Submit button is a placeholder until Stage 2, and a "Weekly regulars" box.
8. **Phones first:** everything works at 390 px wide; touch targets at least 44 px.

**Distance needs town coordinates.** Add a `towns` table with a latitude and longitude for every place name used in `venues.town`, from public Census data. Venue towns include villages that are not among Connecticut's 169 towns (Uncasville, Mashantucket, Mystic, Niantic, Milldale, Winsted, Willimantic and others), so match those too. Town-center precision is fine for v1.

**Look:** dark "venue marquee" style. Background #14110F, text #F3EDE3, secondary text #CFC6B8 and #A89F92, panels #1E1A17, borders #2E2925, one accent #F2B33D. Fonts from Google Fonts: Big Shoulders Display 800 for headings (uppercase), IBM Plex Sans for body, IBM Plex Mono for times and counts. Define these once as design tokens (CSS variables) so branding can change later in one place.

## Feed importer v1

A Python script, run once a day by GitHub Actions, reads every active `ics` row in `sources` and writes its events into `events`. Seven feeds are ready, all tested by hand in October 2026.

| Feed | URL | What to keep and quirks |
| --- | --- | --- |
| Hartford Jazz Society | `https://hartfordjazzsociety.com/events/?ical=1` | All. Some LOCATIONs are incomplete ("MA") |
| CT Examiner | `https://ctexaminer.com/events/?ical=1` | Music only. Ignore DTEND when it is over a day after DTSTART (some say 2028). Check whether the feed pages |
| The MAC, Milford | `https://milfordarts.org/?post_type=tribe_events&ical=1&eventDisplay=list` | Concerts and open mic nites only |
| The Breakwall, West Haven | `https://thebreakwallct.com/events/?ical=1` | Live music only; skip trivia, music bingo and Open Mic Night (a recurring rule covers it). TZID says America/Argentina/Ushuaia but times are Connecticut local |
| The Griswold Inn, Essex | `https://griswoldinn.com/events/?ical=1` | CATEGORIES = Tap Room only. Times labeled UTC but are Connecticut local |
| Bill's Seafood, Westbrook | `https://billsseafood.com/events/?ical=1` | All except special events with no band (Octoberfest) |
| CT Public, Music & Performance | `https://content.ctpublic.org/events/category/music-performance/list/?ical=1` | Statewide; skip plays, musicals, fairs, trivia and galas. Some LOCATIONs say only "CT"; some state codes are cut to "C" |

Rules for every feed:

- **No duplicates:** match on the event's ICS UID (`external_uid`) per source and update the existing row. Shows from The Breakwall, Griswold Inn and Bill's Seafood are already saved with their feed UIDs.
- **Time zones:** read each feed's times as America/New_York unless a feed is known to be right; two feeds mislabel their zone (above).
- **Venues:** match LOCATION to an existing venue by name and town. No match: keep the text in `location_text` and log it for review; never create venues automatically in v1.
- **Out of state:** skip events outside Connecticut, unless a Connecticut band is playing (for example Rum Runners at Daryl's House Club in Pawling, NY).
- **Logging:** set `last_fetched_at` and `last_status` on the source each run, so a broken feed is visible.
- **Firehouse 12** (`https://firehouse12.com/jazz-series?format=ical`) is recorded but inactive; test it, and turn it on only if it returns the whole series.

**Next easiest sources** (recorded in `sources` as inactive scrapers): The Flying Monkey (`/music?format=json`) and The Juke (`/upcoming-events?format=json`) publish Squarespace JSON with exact times, almost as good as a feed. Black Eyed Sally's has a WordPress events API (use the displayed time; the structured time is wrong). Clean pages: Windmill Tavern, Woodbury Brewing (Viewcy), Park City Music Hall, Elicit Brewing's three locations, Rocks 21, Longley's.

## Out of scope for v1

These are decided as later work; don't build them now.

- **Map view:** after launch. Needs each venue geocoded from a street address; many venues have addresses now, but not all. Planned tools: Leaflet with OpenStreetMap.
- **Community submission form (Stage 2):** the Submit button is a placeholder.
- **Website scrapers (Stage 3):** about 20 venue pages are recorded in `sources` as inactive scraper candidates, with notes on each.
- **Facebook:** never scrape it. Ellen checks her Facebook events by hand now and then, and Claude turns what she finds into database updates.
- **Other listing sites:** Shoreline Live Music, Karaoverse and Wailing City are other people's curated work. Ellen plans to contact them about sharing listings; don't scrape them. Shoreline Music Monthly: Ellen is holding off on contacting the publisher. Skip Bandsintown.
- **Venue and band pages, search by name, accounts.**

## Build order

Get a plain site live early, then add pieces one at a time, each one tested before the next.

1. **Catch up the database:** done Oct 13.
2. **Setup:** create the GitHub repository (public) and the project structure; connect to Supabase with the anon key for the site and the service_role key for scripts, both stored as secrets.
3. **Towns:** add the `towns` table with coordinates and confirm every `venues.town` value matches a row.
4. **Homepage:** build it from the design, reading `upcoming_listings`; check it on a phone-sized screen.
5. **Publish:** deploy to Cloudflare Pages at its free address so Ellen can see it live.
6. **Importer:** write the Python ICS importer for the 7 feeds, run it by hand, check the results, then schedule it daily in GitHub Actions.
7. **Launch:** connect the MicCheckCT domain.

## Open data issues

None of these block the build; Ellen can work through them in parallel.

- **Karaoke start times:** most karaoke nights show "Time TBA". Karaoverse lists times for many Connecticut karaoke nights.
- **Every-other-week nights:** 13 karaoke rules are inactive until someone confirms which weeks.
- **Hidden until a town is confirmed:** Sobieski John III Club and Stormy's (one show each); the Riot Kings show at an unnamed Main Street Tavern.
- **Possible duplicate bands:** David Stoltz & Co. / Stolze & Co; Chris Moraldo / Chris Marolda.
- **To confirm:** the venue listed only as "33" (New London); open mic times at JD's Roadhouse and Nightingale's conflict between sources; Firehouse 12's series-wide feed.
- **Sites that show nothing:** Blackstone Irish Pub's site blocks visitors; Anthony D's has no website; Strange Brew, Hard Hat Cafe, Central Cafe and Orange Ale House post shows only on Facebook or Eventbrite.
