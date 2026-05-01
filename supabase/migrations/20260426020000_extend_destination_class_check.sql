-- supabase/migrations/20260426020000_extend_destination_class_check.sql
-- Universal URL Harvester v1: extend the destination_class CHECK constraint
-- on profile_destination_links to accept the 6 new classes added in
-- DestinationClass Literal: commerce, messaging, content, affiliate,
-- professional, unknown. Without this, rows tagged 'messaging' (Telegram,
-- WhatsApp, Discord) crash on insert. Caught by 2026-04-26 smoke.

ALTER TABLE profile_destination_links
  DROP CONSTRAINT IF EXISTS profile_destination_links_destination_class_check;

ALTER TABLE profile_destination_links
  ADD CONSTRAINT profile_destination_links_destination_class_check
  CHECK (destination_class = ANY (ARRAY[
    'monetization'::text,
    'aggregator'::text,
    'social'::text,
    'commerce'::text,
    'messaging'::text,
    'content'::text,
    'affiliate'::text,
    'professional'::text,
    'other'::text,
    'unknown'::text
  ]));
