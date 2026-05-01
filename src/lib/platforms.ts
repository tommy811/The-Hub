// src/lib/platforms.ts — Platform mapping and metadata configuration
import {
  DollarSign,
  Heart,
  ShoppingCart,
  Link as LinkIcon,
  Globe,
  type LucideIcon,
} from "lucide-react";
import type { IconType } from "react-icons";
import {
  SiInstagram,
  SiTiktok,
  SiYoutube,
  SiFacebook,
  SiX,
  SiPatreon,
  SiOnlyfans,
  SiTelegram,
  SiReddit,
  SiThreads,
  SiBluesky,
  SiSnapchat,
  SiSpotify,
  SiSubstack,
  SiDiscord,
  SiWhatsapp,
  SiKofi,
  SiBuymeacoffee,
} from "react-icons/si";
import { FaLinkedin, FaAmazon } from "react-icons/fa6";

export type AccountType =
  | "social"
  | "monetization"
  | "link_in_bio"
  | "messaging"
  | "other";

// BrandIcon may be either a Simple Icons / FontAwesome 6 component (IconType from react-icons)
// or a Lucide component (LucideIcon). Both are functional React components that accept a className,
// size and color/style — so consumers can render them uniformly.
export type BrandIcon = IconType | LucideIcon;

export interface PlatformMetadata {
  label: string;
  color: string;
  bgColor: string;
  icon: BrandIcon;
  accountType: AccountType;
  /**
   * Lower number = earlier in deterministic sort order.
   * 10 = social-primary, 20 = monetization-subscription, 30 = monetization-ecommerce,
   * 40 = link-in-bio, 50 = messaging, 99 = other.
   */
  sortPriority: number;
}

export const PLATFORMS: Record<string, PlatformMetadata> = {
  instagram: {
    label: "Instagram",
    color: "#E1306C",
    bgColor: "rgba(225, 48, 108, 0.1)",
    icon: SiInstagram,
    accountType: "social",
    sortPriority: 10,
  },
  tiktok: {
    label: "TikTok",
    color: "#00f2fe",
    bgColor: "rgba(0, 242, 254, 0.1)",
    icon: SiTiktok,
    accountType: "social",
    sortPriority: 10,
  },
  youtube: {
    label: "YouTube",
    color: "#FF0000",
    bgColor: "rgba(255, 0, 0, 0.1)",
    icon: SiYoutube,
    accountType: "social",
    sortPriority: 10,
  },
  facebook: {
    label: "Facebook",
    color: "#1877F2",
    bgColor: "rgba(24, 119, 242, 0.1)",
    icon: SiFacebook,
    accountType: "social",
    sortPriority: 10,
  },
  twitter: {
    label: "X (Twitter)",
    color: "#FFFFFF",
    bgColor: "rgba(255, 255, 255, 0.08)",
    icon: SiX,
    accountType: "social",
    sortPriority: 10,
  },
  linkedin: {
    label: "LinkedIn",
    // No SiLinkedin in this react-icons (5.6.0) build of /si — fall back to FontAwesome 6 brand glyph.
    color: "#0A66C2",
    bgColor: "rgba(10, 102, 194, 0.1)",
    icon: FaLinkedin,
    accountType: "social",
    sortPriority: 10,
  },
  reddit: {
    label: "Reddit",
    color: "#FF4500",
    bgColor: "rgba(255, 69, 0, 0.1)",
    icon: SiReddit,
    accountType: "social",
    sortPriority: 10,
  },
  threads: {
    label: "Threads",
    color: "#FFFFFF",
    bgColor: "rgba(255, 255, 255, 0.08)",
    icon: SiThreads,
    accountType: "social",
    sortPriority: 10,
  },
  bluesky: {
    label: "Bluesky",
    color: "#1185FE",
    bgColor: "rgba(17, 133, 254, 0.1)",
    icon: SiBluesky,
    accountType: "social",
    sortPriority: 10,
  },
  snapchat: {
    label: "Snapchat",
    color: "#FFFC00",
    bgColor: "rgba(255, 252, 0, 0.1)",
    icon: SiSnapchat,
    accountType: "social",
    sortPriority: 10,
  },
  patreon: {
    label: "Patreon",
    color: "#FF424D",
    bgColor: "rgba(255, 66, 77, 0.1)",
    icon: SiPatreon,
    accountType: "monetization",
    sortPriority: 20,
  },
  onlyfans: {
    label: "OnlyFans",
    color: "#00AFF0",
    bgColor: "rgba(0, 175, 240, 0.1)",
    icon: SiOnlyfans,
    accountType: "monetization",
    sortPriority: 20,
  },
  fanvue: {
    label: "Fanvue",
    // No Simple Icon for Fanvue — fall back to lucide Heart (subscription/creator-fan vibe).
    color: "#FF3366",
    bgColor: "rgba(255, 51, 102, 0.1)",
    icon: Heart,
    accountType: "monetization",
    sortPriority: 20,
  },
  fanplace: {
    label: "Fanplace",
    // No Simple Icon for Fanplace — fall back to lucide Heart.
    color: "#FF4477",
    bgColor: "rgba(255, 68, 119, 0.1)",
    icon: Heart,
    accountType: "monetization",
    sortPriority: 20,
  },
  fanfix: {
    label: "Fanfix",
    // No Si icon — Heart is the convention for fan-platform monetization.
    color: "#FF3366",
    bgColor: "rgba(255, 51, 102, 0.1)",
    icon: Heart,
    accountType: "monetization",
    sortPriority: 20,
  },
  cashapp: {
    label: "Cash App",
    // No Si icon for Cash App.
    color: "#00D632",
    bgColor: "rgba(0, 214, 50, 0.1)",
    icon: DollarSign,
    accountType: "monetization",
    sortPriority: 20,
  },
  venmo: {
    label: "Venmo",
    color: "#3D95CE",
    bgColor: "rgba(61, 149, 206, 0.1)",
    icon: DollarSign,
    accountType: "monetization",
    sortPriority: 20,
  },
  kofi: {
    label: "Ko-fi",
    color: "#FF5E5B",
    bgColor: "rgba(255, 94, 91, 0.1)",
    icon: SiKofi,
    accountType: "monetization",
    sortPriority: 20,
  },
  buymeacoffee: {
    label: "Buy Me a Coffee",
    color: "#FFDD00",
    bgColor: "rgba(255, 221, 0, 0.1)",
    icon: SiBuymeacoffee,
    accountType: "monetization",
    sortPriority: 20,
  },
  amazon_storefront: {
    label: "Amazon Storefront",
    // No SiAmazon in this react-icons (5.6.0) build of /si — fall back to FontAwesome 6.
    color: "#FF9900",
    bgColor: "rgba(255, 153, 0, 0.1)",
    icon: FaAmazon,
    accountType: "monetization",
    sortPriority: 30,
  },
  tiktok_shop: {
    label: "TikTok Shop",
    // TikTok Shop is a TT product — could reuse SiTiktok, but the cart glyph reads better
    // alongside an existing TikTok social row in the same creator footprint.
    color: "#00f2fe",
    bgColor: "rgba(0, 242, 254, 0.1)",
    icon: ShoppingCart,
    accountType: "monetization",
    sortPriority: 30,
  },
  // All link-in-bio aggregators share the unified clip icon — they're "links to
  // links" by definition, so a single visual marker reads cleaner than per-brand
  // glyphs.
  linktree: {
    label: "Linktree",
    color: "#A0A0A0",
    bgColor: "rgba(160, 160, 160, 0.1)",
    icon: LinkIcon,
    accountType: "link_in_bio",
    sortPriority: 40,
  },
  beacons: {
    label: "Beacons",
    color: "#A0A0A0",
    bgColor: "rgba(160, 160, 160, 0.1)",
    icon: LinkIcon,
    accountType: "link_in_bio",
    sortPriority: 40,
  },
  link_me: {
    label: "link.me",
    color: "#A0A0A0",
    bgColor: "rgba(160, 160, 160, 0.1)",
    icon: LinkIcon,
    accountType: "link_in_bio",
    sortPriority: 40,
  },
  tapforallmylinks: {
    label: "Tap For All My Links",
    color: "#A0A0A0",
    bgColor: "rgba(160, 160, 160, 0.1)",
    icon: LinkIcon,
    accountType: "link_in_bio",
    sortPriority: 40,
  },
  allmylinks: {
    label: "AllMyLinks",
    color: "#A0A0A0",
    bgColor: "rgba(160, 160, 160, 0.1)",
    icon: LinkIcon,
    accountType: "link_in_bio",
    sortPriority: 40,
  },
  lnk_bio: {
    label: "Lnk.Bio",
    color: "#A0A0A0",
    bgColor: "rgba(160, 160, 160, 0.1)",
    icon: LinkIcon,
    accountType: "link_in_bio",
    sortPriority: 40,
  },
  snipfeed: {
    label: "Snipfeed",
    color: "#A0A0A0",
    bgColor: "rgba(160, 160, 160, 0.1)",
    icon: LinkIcon,
    accountType: "link_in_bio",
    sortPriority: 40,
  },
  launchyoursocials: {
    label: "Launch Your Socials",
    color: "#A0A0A0",
    bgColor: "rgba(160, 160, 160, 0.1)",
    icon: LinkIcon,
    accountType: "link_in_bio",
    sortPriority: 40,
  },
  custom_domain: {
    label: "Custom Domain",
    color: "#A0A0A0",
    bgColor: "rgba(160, 160, 160, 0.1)",
    icon: LinkIcon,
    accountType: "link_in_bio",
    sortPriority: 40,
  },
  telegram_channel: {
    label: "Telegram Channel",
    color: "#0088cc",
    bgColor: "rgba(0, 136, 204, 0.1)",
    icon: SiTelegram,
    accountType: "messaging",
    sortPriority: 50,
  },
  telegram_cupidbot: {
    label: "Telegram Cupidbot",
    color: "#0088cc",
    bgColor: "rgba(0, 136, 204, 0.1)",
    icon: SiTelegram,
    accountType: "messaging",
    sortPriority: 50,
  },
  discord: {
    label: "Discord",
    color: "#5865F2",
    bgColor: "rgba(88, 101, 242, 0.1)",
    icon: SiDiscord,
    accountType: "messaging",
    sortPriority: 50,
  },
  whatsapp: {
    label: "WhatsApp",
    color: "#25D366",
    bgColor: "rgba(37, 211, 102, 0.1)",
    icon: SiWhatsapp,
    accountType: "messaging",
    sortPriority: 50,
  },
  spotify: {
    label: "Spotify",
    color: "#1DB954",
    bgColor: "rgba(29, 185, 84, 0.1)",
    icon: SiSpotify,
    accountType: "other", // content, not strictly social/monetization
    sortPriority: 60,
  },
  substack: {
    label: "Substack",
    color: "#FF6719",
    bgColor: "rgba(255, 103, 25, 0.1)",
    icon: SiSubstack,
    accountType: "other",
    sortPriority: 60,
  },
  other: {
    label: "Other",
    color: "#888888",
    bgColor: "rgba(136, 136, 136, 0.1)",
    icon: Globe,
    accountType: "other",
    sortPriority: 99,
  },
};

// DollarSign is exported for potential consumers; keep import side-effect-free by referencing it.
// (Tree-shakers drop unused; this just documents the available fallback.)
export const FALLBACK_MONETIZATION_ICON: LucideIcon = DollarSign;

export function getPlatform(p: string | null): PlatformMetadata {
  if (!p) return PLATFORMS.other;
  return PLATFORMS[p.toLowerCase()] || PLATFORMS.other;
}

export function getSortPriority(p: string | null | undefined): number {
  if (!p) return PLATFORMS.other.sortPriority;
  return (PLATFORMS[p.toLowerCase()] ?? PLATFORMS.other).sortPriority;
}

// Inferred-from-URL platform lookup. Used when DB platform is 'other' but the
// URL host is a known platform (e.g. Reddit, Threads, Bluesky, Snapchat —
// anything not in the Postgres `platform` enum but for which we have an icon).
const HOST_PLATFORM_MAP: Record<string, string> = {
  "reddit.com": "reddit",
  "old.reddit.com": "reddit",
  "threads.net": "threads",
  "bsky.app": "bluesky",
  "snapchat.com": "snapchat",
  // T17 — specific aggregator + monetization hosts so even legacy DB rows tagged
  // 'other' or 'custom_domain' surface the right icon/label.
  "link.me": "link_me",
  "tapforallmylinks.com": "tapforallmylinks",
  "allmylinks.com": "allmylinks",
  "lnk.bio": "lnk_bio",
  "snipfeed.co": "snipfeed",
  "launchyoursocials.com": "launchyoursocials",
  "fanfix.io": "fanfix",
  "app.fanfix.io": "fanfix",
  "cash.app": "cashapp",
  "venmo.com": "venmo",
  "ko-fi.com": "kofi",
  "buymeacoffee.com": "buymeacoffee",
  "open.spotify.com": "spotify",
  "spotify.com": "spotify",
  "substack.com": "substack",
  "discord.gg": "discord",
  "discord.com": "discord",
  "wa.me": "whatsapp",
};

export function getPlatformFromUrl(url: string | null | undefined): string | null {
  if (!url) return null;
  try {
    const h = new URL(url).hostname.toLowerCase().replace(/^www\./, "");
    return HOST_PLATFORM_MAP[h] || null;
  } catch {
    return null;
  }
}

// Resolve a (platform, url) pair to PlatformMetadata. If the DB platform is
// 'other' / 'custom_domain' / unknown, fall back to URL-host inference so UI
// surfaces (icon, label, sort priority) still render properly. For a TRULY
// custom funnel domain (no rule match), build an ad-hoc PlatformMetadata using
// the URL host as the label (e.g. "ariaswan.com").
export function resolvePlatform(
  platform: string | null | undefined,
  url: string | null | undefined,
): PlatformMetadata {
  if (
    platform &&
    platform !== "other" &&
    platform !== "custom_domain" &&
    PLATFORMS[platform.toLowerCase()]
  ) {
    return PLATFORMS[platform.toLowerCase()];
  }
  // For 'other' or 'custom_domain', try inferring from URL host first.
  const inferred = getPlatformFromUrl(url);
  if (inferred && PLATFORMS[inferred]) return PLATFORMS[inferred];
  // Fall back: if platform is 'custom_domain' and we have a URL, build an
  // ad-hoc PlatformMetadata using the host as the label.
  if (platform === "custom_domain" && url) {
    try {
      const host = new URL(url).hostname.toLowerCase().replace(/^www\./, "");
      return {
        ...PLATFORMS.custom_domain,
        label: host,
      };
    } catch {
      // fall through to default
    }
  }
  return platform ? getPlatform(platform) : PLATFORMS.other;
}
