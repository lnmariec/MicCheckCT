-- =====================================================================
-- MicCheckCT data update, Nov 2026: bands from Ellen's artist research
-- (ct_artist_website_social_starter.xlsx). Data only; no table changes.
--   - 15 new artists with their websites. Touring acts (is_local = false):
--     The Disco Biscuits, Hayley Jane Band, Duke Robillard, The Garcia Project.
--     Don't Tell Lisa has no site, so its Facebook page is its website.
--   - Websites for 3 artists already saved: Mark Nomad Band, The Cartells, The Cherry Pie Band.
--   - Facebook, Instagram and Bandcamp links go in notes until the table has columns for them.
-- Safe to run twice: existing slugs are skipped and websites only fill blanks.
-- Run in Supabase: SQL Editor > New query > paste > Run
-- =====================================================================

begin;

insert into artists (name, slug, website, is_local, notes) values
  ('Brian Theoret', 'brian-theoret', 'https://briantheoret.com/', true, 'Added Nov 2026 from Ellen''s artist research. Bandcamp/other: https://briantheoret.bandcamp.com/music'),
  ('Don''t Tell Lisa', 'dont-tell-lisa', 'https://www.facebook.com/donttelllisaband', true, 'Added Nov 2026 from Ellen''s artist research.'),
  ('Duke Robillard', 'duke-robillard', 'https://www.dukerobillard.com/', false, 'Added Nov 2026 from Ellen''s artist research.'),
  ('Hayley Jane Band', 'hayley-jane-band', 'https://hayleyjane.com/', false, 'Added Nov 2026 from Ellen''s artist research.'),
  ('Jeff Przech', 'jeff-przech', 'https://jeffprzech.com/', true, 'Added Nov 2026 from Ellen''s artist research.'),
  ('Mystic Dead', 'mystic-dead', 'https://mysticdead.com/', true, 'Added Nov 2026 from Ellen''s artist research.'),
  ('Ramblin'' Dan Stevens', 'ramblin-dan-stevens', 'http://www.danstevens.net/', true, 'Added Nov 2026 from Ellen''s artist research. Facebook: https://www.facebook.com/ramblindanstevens/'),
  ('Sister Funk', 'sister-funk', 'https://sisterfunk.com/', true, 'Added Nov 2026 from Ellen''s artist research.'),
  ('The Alpaca Gnomes', 'the-alpaca-gnomes', 'https://www.thealpacagnomes.com/', true, 'Added Nov 2026 from Ellen''s artist research.'),
  ('The Disco Biscuits', 'the-disco-biscuits', 'https://www.discobiscuits.com/', false, 'Added Nov 2026 from Ellen''s artist research.'),
  ('The Garcia Project', 'the-garcia-project', 'https://www.thegarciaproject.com/', false, 'Added Nov 2026 from Ellen''s artist research.'),
  ('The Subliminals', 'the-subliminals', 'https://www.thesubliminalsband.com/', true, 'Added Nov 2026 from Ellen''s artist research. Facebook: https://www.facebook.com/The-Subliminals-206851506624521/'),
  ('The ToneShifters', 'the-toneshifters', 'https://www.toneshifters.com/', true, 'Added Nov 2026 from Ellen''s artist research. Instagram: https://www.instagram.com/toneshifters/'),
  ('Tony Marshall', 'tony-marshall', 'https://tonymarshallmusic.com/', true, 'Added Nov 2026 from Ellen''s artist research.'),
  ('WE3 Trio', 'we3-trio', 'https://www.we3trio.com/', true, 'Added Nov 2026 from Ellen''s artist research.')
on conflict (slug) do nothing;

update artists set website = 'https://marknomad.com/' where id = '14f29711-8456-4b31-9e28-74a613538cbc' and website is null;  -- Mark Nomad Band
update artists set website = 'https://thecartells.com/' where id = '6dd17136-54b0-4708-87cd-82a1f96945b5' and website is null;  -- The Cartells
update artists set notes = coalesce(notes || ' | ', '') || 'Facebook: https://www.facebook.com/thecartells' where id = '6dd17136-54b0-4708-87cd-82a1f96945b5' and coalesce(notes, '') not like '%Facebook: https://www.facebook.com/thecartells%';  -- The Cartells (skipped if already added)
update artists set website = 'https://www.cherrypieband.com/' where id = 'b06930de-3ff6-4ccb-8cdc-cdbabec1adbb' and website is null;  -- The Cherry Pie Band

commit;
