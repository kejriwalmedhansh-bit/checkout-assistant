# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack

Existing codebase: React frontend (`react/src`), Python/FastAPI backend (`src/`). Not greenfield — no stack decision needed.

## Users

Everyday Indian e-commerce shoppers, mobile-first. Reading comfort varies widely across the real user base; **design for the harder end of that range** — assume many users will not read sentences at all, and icons/numbers/colour must be able to carry the full meaning on their own. Comfortable with online shopping and UPI payments in general — that is not where hesitation comes from. The real hesitation is that **buying a gift voucher is an unfamiliar concept** to most of these users; the product's core trust gap is "is this voucher thing legitimate and does it actually work," not "is it safe to pay online."

## Product Purpose

Dealo is a pre-checkout purchase optimization engine. Input: a product URL or text query. Output: the smartest way to actually buy it — one Recommended Route plus up to 3 alternatives. It is explicitly **not** a cashback platform, coupon site, or credit card business — it generates routes, not discounts.

## Positioning

Stacks gift-voucher arbitrage (via Gyftr, ~380 brands) with cashback-card optimization to find the true lowest final cost, then always surfaces a path that requires no credit card. A neighboring price-comparison tool could not truthfully copy this without the voucher-stacking mechanism — that stacking, not sticker-price comparison, is the actual differentiator.

## Operating Context

Two distinct, **equally strategic** surfaces, each with its own format and conventions — not a single interface ported twice:
- **Web app** (React + FastAPI): the fuller, browsable experience.
- **WhatsApp chatbot**: the product owner is explicitly bullish on WhatsApp chatbots as India's next major interface category. Equal priority to web, but copy, pacing, and interaction patterns should be native to chat, not a reskin of the web flow.

Real merchant/voucher-partner names appear directly in product copy (Gyftr, Tata CLiQ, Myntra, Amazon, etc.) — this is a deliberate, existing pattern, not a placeholder.

## Capabilities and Constraints

Non-negotiable product rules (durable business rules, unlikely to change even as implementation is refactored):
- **Trust is the core product value.** A wrong result is worse than no result.
- **Recommended Route = lowest final cost, always card-free, executable by anyone.** Card-based savings never affect ranking.
- **Alternatives (max 3)**, shown only behind an explicit "not working for you?" toggle — never presented as parallel equal options up front.
- **Card recommendations (L3): direct cashback only** (never points/miles), ranked by actual saving after cap, not headline rate.
- **Never expose backend mechanics in user-facing copy** — no internal layer names, stacking math, or reward-point arithmetic. Users should be able to understand the recommendation in under 10 seconds.
- **No gamification** — no points, badges, streaks, or scratch-to-reveal mechanics. Dealo should read as a serious, trustworthy money tool, established after explicitly trying and rejecting a gamified redemption-flow direction.
- Users may not have premium credit cards; never assume they do.
- No automated tests exist yet; everything is checked by hand. A second developer (not the product owner) currently handles production deploys.

## Brand Commitments

- **Palette ("Ink & Copper"):** background `#FAFAF7`, ink text `#16202B`, brand navy `#1F3A5F`, copper accent `#C1712F` — shipped and live on the real site (not one of the earlier, since-superseded palette explorations).
- **Logo mark:** a ring-and-dot icon connected by a dashed line, wordmark "dealo."
- **Typography used in recent design work:** Rubik (display/headings) + Nunito Sans (body/UI text).

## Evidence on Hand

No live production data was used in recent mockups — the worked example (Nike Air Force 1 '07 via Tata CLiQ Fashion, ₹9,000 voucher paid at ₹7,650, ₹1,345 saved) is illustrative, not pulled from a real transaction. Future work should not treat those specific figures as real evidence.

## Product Principles

1. Design for the lower end of reading comfort by default — icons, numbers, and colour must carry full meaning without relying on sentences.
2. The trust gap to close is "is buying a gift voucher legitimate," not general online-payment anxiety — reassurance should target the voucher step specifically, not payment security broadly.
3. Web and WhatsApp are equally strategic surfaces with genuinely different formats — never force one medium's interaction pattern onto the other.
4. No gamification, ever, without an explicit new ask — this is a serious money tool, not a game.
5. The Recommended Route is always card-free and always the single most important thing on screen; alternatives stay secondary and opt-in.

## Accessibility & Inclusion

No formally required standard stated, but functionally load-bearing: the product must work for users with limited reading comfort/English fluency as a core requirement, not an edge case — see Users and Product Principles above.
