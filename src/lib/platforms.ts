// src/lib/platforms.ts — Platform mapping and metadata configuration
import {
  DollarSign,
  Heart,
  ShoppingCart,
  Link2,
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
  SiLinktree,
  SiTelegram,
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
  linktree: {
    label: "Linktree",
    color: "#43E660",
    bgColor: "rgba(67, 230, 96, 0.1)",
    icon: SiLinktree,
    accountType: "link_in_bio",
    sortPriority: 40,
  },
  beacons: {
    label: "Beacons",
    // No Simple Icon for Beacons — fall back to lucide Link2.
    color: "#FFFFFF",
    bgColor: "rgba(255, 255, 255, 0.1)",
    icon: Link2,
    accountType: "link_in_bio",
    sortPriority: 40,
  },
  custom_domain: {
    label: "Custom Domain",
    color: "#A0A0A0",
    bgColor: "rgba(160, 160, 160, 0.1)",
    icon: Globe,
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
