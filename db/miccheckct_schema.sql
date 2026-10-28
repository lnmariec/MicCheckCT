-- =====================================================================
-- MicCheckCT database schema (v5: towns table; v4: blank start times, artists.is_local, every-N-weeks rules, events.time_tba)
-- Run once in Supabase: Dashboard > SQL Editor > New query > paste > Run
-- =====================================================================
-- Tables:
--   venues             places that host music (from ct_venues_shoreline_updated.csv)
--   artists            bands and performers (from bands_ct.csv)
--   sources            where event data comes from (ICS feeds, scrapers, manual, submissions)
--   events             one-off dated shows
--   event_artists      which artists play which events
--   recurring_events   weekly or monthly rules for open mics, karaoke, jams
--   recurring_exceptions  dates a recurring night is skipped (holidays, cancellations)
--   towns              center point of every town and village, for distance (data: db/towns.sql)
-- View:
--   upcoming_listings  what the website shows: one-off events plus recurring
--                      nights expanded into real dates for the next 60 days
-- =====================================================================


-- ---------------------------------------------------------------------
-- VENUES
-- ---------------------------------------------------------------------
create table venues (
  id            uuid primary key default gen_random_uuid(),
  name          text not null,
  slug          text not null unique,          -- url-friendly name, e.g. 'cafe-nine'
  venue_type    text,                          -- music venue, bar, brewery, casino, arts center...
  address       text,
  town          text not null,
  state         text not null default 'CT',
  website       text,
  phone         text,
  latitude      numeric(9,6),                  -- optional, for a future map
  longitude     numeric(9,6),
  notes         text,                          -- internal notes, not shown publicly
  is_active     boolean not null default true, -- false = closed or no longer listed
  created_at    timestamptz not null default now(),
  updated_at    timestamptz not null default now()
);

create index venues_town_idx on venues (town);


-- ---------------------------------------------------------------------
-- ARTISTS (bands and performers)
-- ---------------------------------------------------------------------
create table artists (
  id            uuid primary key default gen_random_uuid(),
  name          text not null,
  slug          text not null unique,
  website       text,
  genre         text,
  hometown      text,
  is_local      boolean not null default true, -- false = touring act based outside CT
  notes         text,
  created_at    timestamptz not null default now(),
  updated_at    timestamptz not null default now()
);


-- ---------------------------------------------------------------------
-- SOURCES (where each event came from)
-- ---------------------------------------------------------------------
create table sources (
  id              uuid primary key default gen_random_uuid(),
  name            text not null,               -- e.g. 'Hartford Jazz Society ICS'
  source_type     text not null
                  check (source_type in ('ics', 'scraper', 'manual', 'submission')),
  url             text,                        -- feed or page URL
  venue_id        uuid references venues (id) on delete set null,  -- if the source is one venue
  is_active       boolean not null default true,
  last_fetched_at timestamptz,                 -- set by the importer each run
  last_status     text,                        -- 'ok', or the error message
  notes           text,
  created_at      timestamptz not null default now()
);


-- ---------------------------------------------------------------------
-- EVENTS (one-off dated shows)
-- ---------------------------------------------------------------------
create table events (
  id              uuid primary key default gen_random_uuid(),
  title           text not null,
  description     text,
  category        text not null default 'live_music'
                  check (category in ('live_music', 'open_mic', 'karaoke', 'jam_session', 'festival')),
  venue_id        uuid references venues (id) on delete set null,
  location_text   text,                        -- fallback when the venue isn't in our list yet
  start_at        timestamptz not null,
  end_at          timestamptz,
  time_tba        boolean not null default false, -- true = date known, start time not announced
  price_text      text,                        -- '$15', 'Free', '$10 adv / $15 door'
  age_limit       text,                        -- '21+', 'All ages'
  ticket_url      text,
  event_url       text,                        -- the original listing page
  status          text not null default 'published'
                  check (status in ('published', 'pending', 'cancelled', 'hidden')),
  -- where it came from, so re-running an importer updates instead of duplicating
  source_id       uuid references sources (id) on delete set null,
  external_uid    text,                        -- the UID from an ICS feed, or a scraper's own key
  -- Stage 2: community submissions (status starts as 'pending' until approved)
  submitted_by_name  text,
  submitted_by_email text,
  created_at      timestamptz not null default now(),
  updated_at      timestamptz not null default now(),
  unique (source_id, external_uid)
);

create index events_start_idx on events (start_at);
create index events_venue_idx on events (venue_id);


-- ---------------------------------------------------------------------
-- EVENT_ARTISTS (an event can have several acts)
-- ---------------------------------------------------------------------
create table event_artists (
  event_id      uuid not null references events (id) on delete cascade,
  artist_id     uuid not null references artists (id) on delete cascade,
  billing_order smallint,                      -- 1 = headliner
  primary key (event_id, artist_id)
);


-- ---------------------------------------------------------------------
-- RECURRING_EVENTS (rules, not individual dates)
-- e.g. "Karaoke at Anthony D's, every Thursday, 9 PM"
--      "Open mic at The Elm, every Tuesday"
--      "Jazz jam, first Sunday of the month"
-- ---------------------------------------------------------------------
create table recurring_events (
  id              uuid primary key default gen_random_uuid(),
  venue_id        uuid not null references venues (id) on delete cascade,
  title           text not null,               -- 'Karaoke Night', 'Open Mic'
  category        text not null
                  check (category in ('live_music', 'open_mic', 'karaoke', 'jam_session', 'festival')),
  day_of_week     smallint not null check (day_of_week between 0 and 6),  -- 0 = Sunday ... 6 = Saturday
  week_of_month   smallint check (week_of_month in (1, 2, 3, 4, -1)),     -- null = every week, 1 = first, -1 = last
  every_n_weeks   smallint not null default 1 check (every_n_weeks between 1 and 8), -- 2 = every other week
  anchor_date     date,                        -- any one date it happens (needed when every_n_weeks > 1)
  start_time      time,                        -- blank = day known, time TBA
  end_time        time,                        -- may be after midnight (e.g. 01:00)
  host            text,                        -- KJ, host, or house band
  description     text,
  signup_info     text,                        -- 'Sign-up at 7:30, 3 songs each'
  -- verification: recurring nights go stale, so track who confirmed them and when
  confirmed_by    text,                        -- 'Ellen', 'venue website', 'karaoke directory'
  last_verified_at date,
  is_active       boolean not null default true,
  starts_on       date,                        -- optional: first date it runs
  ends_on         date,                        -- optional: last date (seasonal series)
  created_at      timestamptz not null default now(),
  updated_at      timestamptz not null default now()
);

create index recurring_venue_idx on recurring_events (venue_id);


-- ---------------------------------------------------------------------
-- RECURRING_EXCEPTIONS (skip a date without deleting the rule)
-- ---------------------------------------------------------------------
create table recurring_exceptions (
  recurring_event_id uuid not null references recurring_events (id) on delete cascade,
  skip_date          date not null,
  reason             text,
  primary key (recurring_event_id, skip_date)
);


-- ---------------------------------------------------------------------
-- TOWNS (v5): one point per place a visitor can pick, for distance.
-- All 169 CT towns plus the villages and out-of-state towns used in
-- venues.town. Rows are loaded by db/towns.sql.
-- ---------------------------------------------------------------------
create table towns (
  name       text not null,               -- matches venues.town
  state      text not null default 'CT',
  kind       text not null check (kind in ('town', 'village')),  -- village = part of a town
  latitude   numeric(9,6) not null,
  longitude  numeric(9,6) not null,
  primary key (name, state)
);

-- ---------------------------------------------------------------------
-- UPCOMING_LISTINGS view: what the website reads
-- One-off events + recurring rules expanded into dates, next 60 days,
-- all times in Connecticut local time.
-- ---------------------------------------------------------------------
create view upcoming_listings with (security_invoker = true) as
  select e.id, 'event'::text as listing_type, e.title, e.category,
         v.id as venue_id, coalesce(v.name, e.location_text) as venue_name, v.town,
         e.start_at, e.end_at, not e.time_tba as time_known,
         e.price_text, e.ticket_url, e.event_url
  from events e
  left join venues v on v.id = e.venue_id
  where e.status = 'published'
    and e.start_at >= now() - interval '6 hours'
    and e.start_at <  now() + interval '60 days'
  union all
  select r.id, 'recurring'::text, r.title, r.category,
         v.id, v.name, v.town,
         (d.day + coalesce(r.start_time, time '00:00')) at time zone 'America/New_York',
         case
           when r.end_time is null or r.start_time is null then null
           when r.end_time > r.start_time then (d.day + r.end_time) at time zone 'America/New_York'
           else (d.day + 1 + r.end_time) at time zone 'America/New_York'
         end,
         r.start_time is not null,
         null::text, null::text, v.website
  from recurring_events r
  join venues v on v.id = r.venue_id
  cross join lateral (
    select g::date as day
    from generate_series((now() at time zone 'America/New_York')::date,
                         (now() at time zone 'America/New_York')::date + 60,
                         interval '1 day') as g
  ) d
  where r.is_active and v.is_active
    and extract(dow from d.day) = r.day_of_week
    and (r.starts_on is null or d.day >= r.starts_on)
    and (r.ends_on   is null or d.day <= r.ends_on)
    and (coalesce(r.every_n_weeks, 1) = 1 or r.anchor_date is null
      or mod(d.day - r.anchor_date, 7 * r.every_n_weeks) = 0)
    and (r.week_of_month is null
      or (r.week_of_month > 0 and ceil(extract(day from d.day) / 7.0) = r.week_of_month)
      or (r.week_of_month = -1 and extract(month from d.day + 7) <> extract(month from d.day)))
    and not exists (select 1 from recurring_exceptions x
                    where x.recurring_event_id = r.id and x.skip_date = d.day);

-- ---------------------------------------------------------------------
-- SECURITY (Row Level Security)
-- The website uses Supabase's public "anon" key, which anyone can see.
-- These rules let the public READ listings and nothing else.
-- Your importers (GitHub Actions) use the secret service_role key,
-- which bypasses these rules and can write.
-- ---------------------------------------------------------------------
alter table venues               enable row level security;
alter table artists              enable row level security;
alter table sources              enable row level security;
alter table events               enable row level security;
alter table event_artists        enable row level security;
alter table recurring_events     enable row level security;
alter table recurring_exceptions enable row level security;
alter table towns                enable row level security;

create policy "public can read active venues"
  on venues for select to anon, authenticated using (is_active);

create policy "public can read artists"
  on artists for select to anon, authenticated using (true);

create policy "public can read published events"
  on events for select to anon, authenticated using (status = 'published');

create policy "public can read event artists"
  on event_artists for select to anon, authenticated using (true);

create policy "public can read active recurring events"
  on recurring_events for select to anon, authenticated using (is_active);

create policy "public can read recurring exceptions"
  on recurring_exceptions for select to anon, authenticated using (true);

create policy "public can read towns"
  on towns for select to anon, authenticated using (true);

-- sources has no public policy: it stays private (feed URLs, error logs).
-- Stage 2 will add one policy letting the public INSERT events with status 'pending'.

grant select on upcoming_listings to anon, authenticated;
grant select on towns to anon, authenticated;
