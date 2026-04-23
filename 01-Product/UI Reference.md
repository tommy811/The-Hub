# UI Reference

## Aesthetic
- Background: `#0A0A0F` (deep near-black)
- Card surface: `#13131A` (slightly lifted)
- Border: `border-white/[0.06]` (very subtle)
- Accent: indigo-500 / violet-500 gradient
- Radius: `rounded-xl` on cards
- No glassmorphism — clean and serious
- Dark mode default: `class="dark"` on `<html>`

## Rank Tier Colors
| Tier | Color |
|---|---|
| Diamond | cyan / white gradient |
| Platinum | teal / mint |
| Gold | amber / yellow |
| Silver | slate / white |
| Bronze | copper / brown |
| Plastic | gray |

## Tracking Type Colors
| Type | Color |
|---|---|
| managed | indigo |
| competitor | red |
| inspiration | violet |
| candidate | amber |
| coach | green |
| hybrid_ai | cyan |
| unreviewed | gray |

## Card States
- **Processing:** skeleton shimmer + Loader2 spinner top-right + opacity-60
- **Ready:** full card with avatar, stats, pills, hover lift + indigo glow
- **Failed:** border-red-900/60 + AlertCircle icon + Retry button

## Key Components Built
- RankBadge — 6 SVG insignia designs per tier
- AccountCard — platform accounts (Phase 1 existing)
- TrackingTabBar — tab bar with count badges
- RankFilterChips — multi-select rank filter
- StatCardRow — 4-card stat strip
- Sidebar — full IA with disabled "soon" items

## Reference App
Inspired by: Linear, Vercel dashboard, high-end CRM tools
Internal reference: Franklin's dashboard (tracking type taxonomy, rank system)
