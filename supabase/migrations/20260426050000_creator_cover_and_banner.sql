-- Foundation for creator visual identity. cover_image_url is scraper-set
-- (banner pulled from FB/Twitter/Reddit when available — Phase 3 work).
-- banner_url is agency-managed override (Simon uploads a high-quality banner).
-- Same pattern for avatar_url (already on profiles) vs override_avatar_url.
ALTER TABLE creators
  ADD COLUMN cover_image_url TEXT,
  ADD COLUMN banner_url TEXT,
  ADD COLUMN override_avatar_url TEXT;

COMMENT ON COLUMN creators.cover_image_url IS 'Scraper-populated banner from FB/Twitter/Reddit etc. Currently null pending scraper work.';
COMMENT ON COLUMN creators.banner_url IS 'Agency-managed banner override (manual upload). Wins over cover_image_url for display.';
COMMENT ON COLUMN creators.override_avatar_url IS 'Agency-managed headshot override. Wins over scraped avatar_url for display.';
