-- =====================================================================
-- MicCheckCT data update, Nov 1 2026: venue cleanup. Data only; no table changes.
--   - Websites Ellen supplied for Highliner lll and Nightingale's Acoustic Cafe
--   - Delete Dexter's (East Hampton): reported closed by March 31 2026.
--     Its Thursday 7 PM open mic rule is deleted with it.
--   - Delete The New Cambridge Project (Bristol): old name of The Factory
--     Brewing Collective, which is already its own venue. Nothing attached.
-- Each line names the venue by id and name, so it can't touch anything else.
-- Run in Supabase: SQL Editor > New query > paste > Run
-- =====================================================================

begin;

update venues set website = 'https://www.thehighliner3.com/'
  where id = (select id from venues where name = 'Highliner lll' and town = 'Westbrook');

update venues set website = 'https://www.musicnowfoundation.org/cafe'
  where id = (select id from venues where name = 'Nightingale''s Acoustic Cafe' and town = 'Old Lyme');

delete from venues
  where id = '29015902-6ace-41a0-9851-89929924861a' and name = 'Dexter''s' and town = 'East Hampton';

delete from venues
  where id = 'a7d66049-4635-49cc-b7be-7d48da8fa4c8' and name = 'The New Cambridge Project' and town = 'Bristol';

commit;
