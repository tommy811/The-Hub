// src/lib/platforms.ts — Platform mapping and metadata configuration
import {
  Camera,
  Music2,
  MonitorPlay,
  DollarSign,
  Heart,
  ShoppingBag,
  ShoppingCart,
  Link as LinkIcon,
  Send,
  MessageSquare,
  Briefcase,
  Users,
  Globe,
  type LucideIcon,
} from "lucide-react";

export type AccountType =
  | "social"
  | "monetization"
  | "link_in_bio"
  | "messaging"
  | "other";

export interface PlatformMetadata {
  label: string;
  color: string;
  bgColor: string;
  icon: LucideIcon;
  accountType: AccountType;
}

export const PLATFORMS: Record<string, PlatformMetadata> = {
  instagram: {
    label: "Instagram",
    color: "#E1306C",
    bgColor: "rgba(225, 48, 108, 0.1)",
    icon: Camera,
    accountType: "social",
  },
  tiktok: {
    label: "TikTok",
    color: "#00f2fe",
    bgColor: "rgba(0, 242, 254, 0.1)",
    icon: Music2,
    accountType: "social",
  },
  youtube: {
    label: "YouTube",
    color: "#FF0000",
    bgColor: "rgba(255, 0, 0, 0.1)",
    icon: MonitorPlay,
    accountType: "social",
  },
  facebook: {
    label: "Facebook",
    color: "#1877F2",
    bgColor: "rgba(24, 119, 242, 0.1)",
    icon: Users,
    accountType: "social",
  },
  twitter: {
    label: "X (Twitter)",
    color: "#1DA1F2",
    bgColor: "rgba(29, 161, 242, 0.1)",
    icon: MessageSquare,
    accountType: "social",
  },
  linkedin: {
    label: "LinkedIn",
    color: "#0A66C2",
    bgColor: "rgba(10, 102, 194, 0.1)",
    icon: Briefcase,
    accountType: "social",
  },
  onlyfans: {
    label: "OnlyFans",
    color: "#00AFF0",
    bgColor: "rgba(0, 175, 240, 0.1)",
    icon: DollarSign,
    accountType: "monetization",
  },
  fanvue: {
    label: "Fanvue",
    color: "#FF3366",
    bgColor: "rgba(255, 51, 102, 0.1)",
    icon: Heart,
    accountType: "monetization",
  },
  fanplace: {
    label: "Fanplace",
    color: "#FF4477",
    bgColor: "rgba(255, 68, 119, 0.1)",
    icon: Heart,
    accountType: "monetization",
  },
  amazon_storefront: {
    label: "Amazon Storefront",
    color: "#FF9900",
    bgColor: "rgba(255, 153, 0, 0.1)",
    icon: ShoppingBag,
    accountType: "monetization",
  },
  tiktok_shop: {
    label: "TikTok Shop",
    color: "#00f2fe",
    bgColor: "rgba(0, 242, 254, 0.1)",
    icon: ShoppingCart,
    accountType: "monetization",
  },
  linktree: {
    label: "Linktree",
    color: "#43E660",
    bgColor: "rgba(67, 230, 96, 0.1)",
    icon: LinkIcon,
    accountType: "link_in_bio",
  },
  beacons: {
    label: "Beacons",
    color: "#000000",
    bgColor: "rgba(255, 255, 255, 0.1)",
    icon: LinkIcon,
    accountType: "link_in_bio",
  },
  telegram_channel: {
    label: "Telegram Channel",
    color: "#0088cc",
    bgColor: "rgba(0, 136, 204, 0.1)",
    icon: Send,
    accountType: "messaging",
  },
  telegram_cupidbot: {
    label: "Telegram Cupidbot",
    color: "#0088cc",
    bgColor: "rgba(0, 136, 204, 0.1)",
    icon: Send,
    accountType: "messaging",
  },
  custom_domain: {
    label: "Custom Domain",
    color: "#A0A0A0",
    bgColor: "rgba(160, 160, 160, 0.1)",
    icon: Globe,
    accountType: "link_in_bio",
  },
  other: {
    label: "Other",
    color: "#888888",
    bgColor: "rgba(136, 136, 136, 0.1)",
    icon: Globe,
    accountType: "other",
  },
};

export function getPlatform(p: string | null): PlatformMetadata {
  if (!p) return PLATFORMS.other;
  return PLATFORMS[p.toLowerCase()] || PLATFORMS.other;
}
