# Enum Reference

## platform (~37 values post-2026-04-26)
**V1 scraped:** instagram, tiktok
**Future scraped:** youtube, facebook, twitter, linkedin, patreon
**Other social (T17, 2026-04-26):** snapchat, reddit, threads, bluesky
**Monetization (tracked, not scraped):** onlyfans, fanvue, fanplace, amazon_storefront, tiktok_shop, fanfix, cashapp, venmo, kofi, buymeacoffee
**Link-in-bio (generic):** linktree, beacons, custom_domain
**Link-in-bio (specific aggregators, T17 2026-04-26):** link_me, tapforallmylinks, allmylinks, lnk_bio, snipfeed, launchyoursocials
**Content platforms (T17, 2026-04-26):** spotify, substack
**Messaging:** telegram_channel, telegram_cupidbot, discord, whatsapp
**Catch-all:** other

The 19 values added on 2026-04-26 (migration `20260426040000_add_platform_values_specific_aggregators_and_monetization`) collapse what used to live as `custom_domain` / `other` into specific identifications. Each has a corresponding entry in `src/lib/platforms.ts` PLATFORMS dict (with Si* / lucide icon) and a host→platform rule in `data/monetization_overlay.yaml` so the resolver classifies them precisely instead of bucketing.

> **Pydantic mirror:** `scripts/schemas.py` declares `Platform = Literal[...]` matching this enum exactly. Future enum extensions must update both — see PROJECT_STATE §20 for the CI-diff future-work note.

---

## account_type
| Value | Platforms | Notes |
|---|---|---|
| social | instagram, tiktok, youtube, facebook, twitter, linkedin | Content accounts |
| monetization | onlyfans, fanvue, fanplace, amazon_storefront, tiktok_shop, patreon | Revenue assets |
| link_in_bio | linktree, beacons, custom_domain | Traffic aggregators |
| messaging | telegram_channel, telegram_cupidbot | Community/DM channels |
| other | other | Catch-all |

---

## onboarding_status
| Value | Meaning |
|---|---|
| processing | Gemini discovery is running — card shows skeleton + spinner |
| ready | Full network discovered — card shows all data |
| failed | Pipeline errored — card shows red border + Retry button |
| archived | Soft-deleted (or merged into another creator) |

---

## tracking_type
| Value | Operational Meaning |
|---|---|
| managed | Agency actively manages this creator |
| inspiration | Reference accounts to study for content ideas |
| competitor | Competing creators in the same niche |
| candidate | Potential talent to sign |
| hybrid_ai | AI-assisted management hybrid |
| coach | Mentor or coaching accounts |
| unreviewed | Freshly imported, not yet classified |

---

## rank_tier (score thresholds 0–100)
| Tier | Min Score | Badge Color |
|---|---|---|
| diamond | 85 | cyan / white |
| platinum | 70 | teal / mint |
| gold | 55 | amber / yellow |
| silver | 40 | slate / white |
| bronze | 25 | copper / brown |
| plastic | 0 | gray |

---

## post_type
reel, tiktok_video, image, carousel, story, story_highlight, youtube_short, youtube_long, other

---

## content_archetype (Jungian 12)
| Value | Description |
|---|---|
| the_jester | Entertains through humor, irreverence, and fun |
| the_caregiver | Nurtures, helps, and supports others |
| the_lover | Creates intimacy, beauty, and sensuality |
| the_everyman | Relatable, down-to-earth, belonging |
| the_creator | Expresses originality, vision, and craft |
| the_hero | Overcomes challenges, inspires through strength |
| the_sage | Shares wisdom, knowledge, and insight |
| the_innocent | Optimistic, wholesome, pure, nostalgic |
| the_explorer | Seeks freedom, adventure, and discovery |
| the_rebel | Challenges norms, disrupts, provokes |
| the_magician | Transforms, manifests, creates change |
| the_ruler | Commands authority, prestige, leadership |

---

## content_vibe
playful, girl_next_door, body_worship, wifey,
luxury, edgy, wholesome, mysterious, confident, aspirational

---

## content_category
comedy_entertainment, fashion_style, fitness, lifestyle,
beauty, travel, food, music, gaming, education, other

---

## monetization_model
subscription, tips, ppv, affiliate, brand_deals,
ecommerce, coaching, saas, mixed, unknown

---

## discovery_run_status
pending → processing → completed | failed

## merge_candidate_status
pending → merged | dismissed

## workspace_role
owner, admin, member

## signal_type
velocity_spike, outlier_post, emerging_archetype,
hook_pattern, cadence_change, new_monetization_detected

## label_type
content_format, trend_pattern, hook_style, visual_style, creator_niche, other

## trend_type
audio, dance, lipsync, transition, meme, challenge

*Powers the `trends` table. `scraped_content.trend_id` FKs into `trends` to link posts to canonical trends.*

## llm_model
gemini_pro, gemini_flash, claude_opus, claude_sonnet

*Reserved for analysis pipelines. Every analysis row will record its generating model in `model_version` so we can A/B test later.*

## edge_type
link_in_bio, direct_link, cta_mention, qr_code, inferred

*Kinds of `funnel_edges` between profiles.*

---

## destination_class (TEXT with CHECK constraint, **not** a Postgres ENUM)

monetization, aggregator, social, commerce, messaging, content, affiliate, professional, other, unknown

*Lives on `profile_destination_links.destination_class`. Extended from 4 → 10 values on 2026-04-26 (migration `20260426020000`) to back the Universal URL Harvester. Implemented as a TEXT column with a CHECK constraint rather than a Postgres ENUM so forward-compat additions are a single `DROP CONSTRAINT / ADD CONSTRAINT` swap instead of `ALTER TYPE ... ADD VALUE` ceremony.*

| Value | Used for |
|---|---|
| monetization | OF, Patreon, Fanvue, paid subs |
| aggregator | Linktree, Beacons, link.me, custom-domain link-in-bio |
| social | IG, TikTok, YouTube, FB, X, LinkedIn |
| commerce | Shopify, Etsy, Depop, owned storefronts |
| messaging | Telegram, WhatsApp, Discord |
| content | Substack, Spotify, Apple Podcasts, Medium, Ghost |
| affiliate | amzn.to, geni.us, lnk.to, shareasale, skimresources |
| professional | LinkedIn, Calendly, Notion press kits |
| other | catch-all for non-matched |
| unknown | classifier returned no confident guess |
