-- MicCheckCT data update, Nov 1 2026: website Ellen supplied for The Stomping Ground (Putnam).
-- Run in Supabase: SQL Editor > New query > paste > Run

update venues set website = 'https://the-stomping-ground.com/'
  where id = (select id from venues where name = 'The Stomping Ground' and town = 'Putnam');
