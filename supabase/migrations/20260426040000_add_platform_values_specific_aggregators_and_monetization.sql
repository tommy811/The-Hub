-- Extends platform enum with specific aggregator + monetization values so
-- they don't all collapse into 'other'. The unique constraint on profiles
-- (workspace_id, platform, handle) needs platform diversity to avoid url
-- collisions between Fanfix + link.me + Cash App etc.
ALTER TYPE platform ADD VALUE IF NOT EXISTS 'link_me';
ALTER TYPE platform ADD VALUE IF NOT EXISTS 'tapforallmylinks';
ALTER TYPE platform ADD VALUE IF NOT EXISTS 'allmylinks';
ALTER TYPE platform ADD VALUE IF NOT EXISTS 'lnk_bio';
ALTER TYPE platform ADD VALUE IF NOT EXISTS 'snipfeed';
ALTER TYPE platform ADD VALUE IF NOT EXISTS 'launchyoursocials';
ALTER TYPE platform ADD VALUE IF NOT EXISTS 'fanfix';
ALTER TYPE platform ADD VALUE IF NOT EXISTS 'cashapp';
ALTER TYPE platform ADD VALUE IF NOT EXISTS 'venmo';
ALTER TYPE platform ADD VALUE IF NOT EXISTS 'snapchat';
ALTER TYPE platform ADD VALUE IF NOT EXISTS 'reddit';
ALTER TYPE platform ADD VALUE IF NOT EXISTS 'spotify';
ALTER TYPE platform ADD VALUE IF NOT EXISTS 'threads';
ALTER TYPE platform ADD VALUE IF NOT EXISTS 'bluesky';
ALTER TYPE platform ADD VALUE IF NOT EXISTS 'kofi';
ALTER TYPE platform ADD VALUE IF NOT EXISTS 'buymeacoffee';
ALTER TYPE platform ADD VALUE IF NOT EXISTS 'substack';
ALTER TYPE platform ADD VALUE IF NOT EXISTS 'discord';
ALTER TYPE platform ADD VALUE IF NOT EXISTS 'whatsapp';
