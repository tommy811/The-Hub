export const RANK_TIERS = ['diamond', 'platinum', 'gold', 'silver', 'bronze', 'plastic'] as const;
export type RankTier = typeof RANK_TIERS[number];

export const RANK_THEMES: Record<RankTier, { bg: string; border: string; text: string; glow: string; gradient: string }> = {
  diamond: {
    bg: 'bg-[#00f2fe]/10',
    border: 'border-[#00f2fe]/30',
    text: 'text-[#00f2fe]',
    glow: 'hover:shadow-[0_0_20px_rgba(0,242,254,0.3)]',
    gradient: 'from-[#00f2fe] to-white'
  },
  platinum: {
    bg: 'bg-[#2af598]/10',
    border: 'border-[#2af598]/30',
    text: 'text-[#2af598]',
    glow: 'hover:shadow-[0_0_20px_rgba(42,245,152,0.3)]',
    gradient: 'from-[#2af598] to-[#009efd]'
  },
  gold: {
    bg: 'bg-[#f6d365]/10',
    border: 'border-[#f6d365]/30',
    text: 'text-[#f6d365]',
    glow: 'hover:shadow-[0_0_20px_rgba(246,211,101,0.3)]',
    gradient: 'from-[#f6d365] to-[#fda085]'
  },
  silver: {
    bg: 'bg-slate-300/10',
    border: 'border-slate-300/30',
    text: 'text-slate-300',
    glow: 'hover:shadow-[0_0_20px_rgba(203,213,225,0.3)]',
    gradient: 'from-slate-300 to-white'
  },
  bronze: {
    bg: 'bg-[#b07c65]/10',
    border: 'border-[#b07c65]/30',
    text: 'text-[#b07c65]',
    glow: 'hover:shadow-[0_0_20px_rgba(176,124,101,0.3)]',
    gradient: 'from-[#b07c65] to-[#8b5a45]'
  },
  plastic: {
    bg: 'bg-zinc-500/10',
    border: 'border-zinc-500/30',
    text: 'text-zinc-500',
    glow: 'hover:shadow-[0_0_20px_rgba(113,113,122,0.3)]',
    gradient: 'from-zinc-500 to-zinc-400'
  }
};

export const RANK_THRESHOLDS = {
  diamond: 85,
  platinum: 70,
  gold: 55,
  silver: 40,
  bronze: 25,
  plastic: 0
};
