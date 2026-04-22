// src/lib/handleParser.ts — Raw handle and URL parsing logic
export type ParsedHandle = {
  handle: string | null;
  platform: string | null;
  url: string | null;
  rawInput: string;
  needsPlatformHint: boolean;
  isDuplicate: boolean;
};

const DOMAIN_TO_PLATFORM: Record<string, string> = {
  "instagram.com": "instagram",
  "tiktok.com": "tiktok",
  "youtube.com": "youtube",
  "youtu.be": "youtube",
  "facebook.com": "facebook",
  "twitter.com": "twitter",
  "x.com": "twitter",
  "linkedin.com": "linkedin",
  "onlyfans.com": "onlyfans",
  "fanvue.com": "fanvue",
  "fanplace.com": "fanplace",
  "amazon.com/shop": "amazon_storefront",
  "linktr.ee": "linktree",
  "beacons.ai": "beacons",
  "t.me": "telegram_channel",
  "bio.link": "custom_domain",
  "taplink.cc": "custom_domain",
};

const PREFIX_TO_PLATFORM: Record<string, string> = {
  ig: "instagram",
  tt: "tiktok",
  yt: "youtube",
  fb: "facebook",
  tw: "twitter",
  li: "linkedin",
  of: "onlyfans",
  fv: "fanvue",
  fp: "fanplace",
  lt: "linktree",
  tg: "telegram_channel",
};

export function parseHandles(
  raw: string,
  existingHandles: Set<string> = new Set()
): ParsedHandle[] {
  if (!raw) return [];

  const lines = raw.split("\n").map((line) => line.trim()).filter(Boolean);
  const results: ParsedHandle[] = [];

  for (const line of lines) {
    const result: ParsedHandle = {
      handle: null,
      platform: null,
      url: null,
      rawInput: line,
      needsPlatformHint: true,
      isDuplicate: false,
    };

    try {
      // 1. Try URL parsing
      if (line.startsWith("http://") || line.startsWith("https://")) {
        const urlObj = new URL(line);
        result.url = line;
        
        let targetDomain = urlObj.hostname.replace(/^www\./, "");
        const pathSegments = urlObj.pathname.split("/").filter(Boolean);

        // Special case for Amazon Storefront
        if (targetDomain === "amazon.com" && pathSegments[0] === "shop") {
          result.platform = "amazon_storefront";
          result.handle = pathSegments[1] || null;
        } else {
          // Standard domain check
          for (const [domain, platform] of Object.entries(DOMAIN_TO_PLATFORM)) {
            if (targetDomain === domain || targetDomain.endsWith(`.${domain}`)) {
              result.platform = platform;
              // Simple extraction rule: usually first path segment + optional query
              if (pathSegments.length > 0) {
                 result.handle = pathSegments[0].replace(/^@/, "");
              }
              break;
            }
          }
        }
      } 
      // 2. Try Prefix/Hint parsing (e.g., ig:username, @username tiktok)
      else if (line.includes(":")) {
        const [prefix, ...rest] = line.split(":");
        const p = prefix.toLowerCase();
        if (PREFIX_TO_PLATFORM[p]) {
          result.platform = PREFIX_TO_PLATFORM[p];
          result.handle = rest.join(":").replace(/^@/, "").trim();
        }
      } 
      // 3. Try space-separated hint (e.g., @glamourqueen tiktok)
      else if (line.includes(" ")) {
        const parts = line.split(/\s+/);
        // Assume first part is handle, later parts might be platform hint
        result.handle = parts[0].replace(/^@/, "");
        const potentialHint = parts[parts.length - 1].toLowerCase();
        
        // Find if potential hint matches a platform explicitly
        const knownPlatforms = new Set([...Object.values(DOMAIN_TO_PLATFORM), ...Object.values(PREFIX_TO_PLATFORM)]);
        if (knownPlatforms.has(potentialHint)) {
            result.platform = potentialHint;
        }
      }
      // 4. Fallback to bare handle
      else {
        result.handle = line.replace(/^@/, "");
      }
    } catch (e) {
      // If URL parsing fails or other issues, fallback to treating as bare handle
      result.handle = line.replace(/^@/, "");
    }

    if (result.platform) {
      result.needsPlatformHint = false;
    }

    if (result.handle && result.platform) {
       const uniqueKey = `${result.platform}:${result.handle}`.toLowerCase();
       if (existingHandles.has(uniqueKey)) {
           result.isDuplicate = true;
       }
    }

    results.push(result);
  }

  return results;
}
