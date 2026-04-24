# Enum Reference

## platform
**V1 scraped:** instagram, tiktok
**Future scraped:** youtube, facebook, twitter, linkedin, patreon
**Monetization (tracked, not scraped):** onlyfans, fanvue, fanplace, amazon_storefront, tiktok_shop
**Link-in-bio:** linktree, beacons, custom_domain
**Messaging:** telegram_channel, telegram_cupidbot
**Catch-all:** other

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
