-- =====================================================================
-- MicCheckCT data update, Oct 29 2026: Robin Clark's weekly list
-- (Thu Oct 29 to Sun Nov 1). Data only; no table changes.
--   - 1 new private source: Robin Clark's weekly list
--   - 8 new venues (name and town only; address and website not checked yet)
--   - 30 new shows (21 at existing venues, 9 at the new ones)
-- Skipped: 7 shows already listed from the venue's own site (their times
-- are kept), and Twisted Cow in East Northport, NY (out of state).
-- Assumed: Kinsmen's "7:30 AM" means PM; Saturday's "Joey C's" is
-- Joey C's Boathouse, Stratford.
-- Safe to run twice: nothing is added a second time.
-- Run in Supabase: SQL Editor > New query > paste > Run
-- =====================================================================

begin;

insert into sources (name, source_type, is_active, notes)
select 'Robin Clark''s weekly list', 'manual', false,
       'Printed weekly list of shows from Robin Clark, sent to Ellen as a photo. Entered by hand.'
where not exists (select 1 from sources where name = 'Robin Clark''s weekly list');

insert into venues (name, slug, venue_type, town, notes) values
  ('Terrazza Restaurant', 'terrazza-restaurant', 'bar/restaurant', 'Portland',    'Added from Robin Clark''s list, Oct 29 2026. Address and website not checked yet.'),
  ('Crush Winery',        'crush-winery',        'winery',         'Wallingford', 'Added from Robin Clark''s list, Oct 29 2026. Address and website not checked yet.'),
  ('Sly Fox Tavern',      'sly-fox-tavern',      'bar/restaurant', 'North Haven', 'Added from Robin Clark''s list, Oct 29 2026. Address and website not checked yet.'),
  ('Kinsmen',             'kinsmen',             'unknown',        'Southington', 'Added from Robin Clark''s list, Oct 29 2026. Address and website not checked yet.'),
  ('Truck Bar',           'truck-bar',           'bar/restaurant', 'Berlin',      'Added from Robin Clark''s list, Oct 29 2026. Address and website not checked yet.'),
  ('Crabby Al''s',        'crabby-als',          'unknown',        'Thomaston',   'Added from Robin Clark''s list, Oct 29 2026. Address and website not checked yet.'),
  ('Brass & Bone',        'brass-and-bone',      'unknown',        'Norwalk',     'Added from Robin Clark''s list, Oct 29 2026. Address and website not checked yet.'),
  ('12 Percent',          '12-percent',          'unknown',        'North Haven', 'Added from Robin Clark''s list, Oct 29 2026. Address and website not checked yet.')
on conflict (slug) do nothing;

-- Each show: venue name and town (must match venues exactly), local start time, act.
create temporary table robin_shows (venue text, town text, starts text, title text) on commit drop;
insert into robin_shows values
  -- Thursday Oct 29
  ('The Kate',                    'Old Saybrook', '2026-10-29 15:00', 'Almighty Queen'),
  ('Scotch Plains Tavern',        'Essex',        '2026-10-29 17:30', 'We 3'),
  ('Highliner lll',               'Westbrook',    '2026-10-29 19:00', 'The Engine Room'),
  ('Infinity Hall',               'Hartford',     '2026-10-29 19:00', 'The Disco Biscuits'),
  ('The Kate',                    'Old Saybrook', '2026-10-29 19:30', 'Almighty Queen'),
  -- Friday Oct 30
  ('Crush Winery',                'Wallingford',  '2026-10-30 17:30', 'Kieran Davey'),
  ('New England Brewing',         'Woodbridge',   '2026-10-30 18:00', 'Rum Runners'),
  ('Terrazza Restaurant',         'Portland',     '2026-10-30 18:30', 'Bad Mannerz'),
  ('Highliner lll',               'Westbrook',    '2026-10-30 19:00', 'Jen & Tonic'),
  ('Winchester',                  'Portland',     '2026-10-30 19:00', 'We 3'),
  ('Sly Fox Tavern',              'North Haven',  '2026-10-30 19:00', 'Ross & Bost'),
  ('Kinsmen',                     'Southington',  '2026-10-30 19:30', 'Spellbound'),
  ('Truck Bar',                   'Berlin',       '2026-10-30 20:00', 'Kisstory'),
  ('The Kate',                    'Old Saybrook', '2026-10-30 20:00', 'DDXS'),
  ('Infinity Hall',               'Hartford',     '2026-10-30 20:00', 'Alpaca Gnomes'),
  ('Crabby Al''s',                'Thomaston',    '2026-10-30 20:00', 'LiveWired'),
  ('Comix Roadhouse',             'Uncasville',   '2026-10-30 21:00', 'Sister Funk'),
  ('Joey C''s Boathouse',         'Stratford',    '2026-10-30 21:00', 'Pop Rocks'),
  ('Brass & Bone',                'Norwalk',      '2026-10-30 21:00', 'Tangled Vine'),
  -- Saturday Oct 31
  ('Highliner lll',               'Westbrook',    '2026-10-31 19:00', 'Bad Mannerz'),
  ('Casa Mia at the Hawthorne',   'Berlin',       '2026-10-31 19:00', 'Downtown 6'),
  ('Hard Hat Cafe (North Haven)', 'North Haven',  '2026-10-31 20:00', 'FB Lily'),
  ('Malone''s',                   'Clinton',      '2026-10-31 20:00', '4 in a Row'),
  ('Scotch Plains Tavern',        'Essex',        '2026-10-31 20:00', 'Don''t Tell Lisa'),
  ('Broad Brook Opera House',     'East Windsor', '2026-10-31 20:00', 'Dio Rules'),
  ('Anthony D''s',                'Milford',      '2026-10-31 21:00', 'Shameless'),
  ('Joey C''s Boathouse',         'Stratford',    '2026-10-31 21:00', 'What Up Funk'),
  -- Sunday Nov 1
  ('12 Percent',                  'North Haven',  '2026-11-01 10:00', 'Rob Glassman Trio'),
  ('Winchester',                  'Portland',     '2026-11-01 14:00', 'Bad Mannerz'),
  ('Crush Winery',                'Wallingford',  '2026-11-01 14:30', 'Rich DiPalma');

-- Stop and undo everything if any venue name doesn't match exactly one venue.
do $$
declare bad text;
begin
  select string_agg(s.venue || ' (' || s.town || ')', ', ') into bad
  from robin_shows s
  where (select count(*) from venues v where v.name = s.venue and v.town = s.town) <> 1;
  if bad is not null then
    raise exception 'No single venue matches: %', bad;
  end if;
end $$;

insert into events (title, category, venue_id, start_at, source_id, external_uid)
select s.title, 'live_music', v.id,
       (s.starts || ':00')::timestamp at time zone 'America/New_York',
       src.id,
       'robin-clark:' || v.slug || ':' || replace(s.starts, ' ', 'T')
from robin_shows s
join venues v on v.name = s.venue and v.town = s.town
cross join (select id from sources where name = 'Robin Clark''s weekly list') src
on conflict (source_id, external_uid) do nothing;

commit;
