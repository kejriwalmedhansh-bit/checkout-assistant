# Dealo Design System — "The Ledger"

Source of truth for Dealo's visual identity. This documents what's actually
implemented in `react/src/theme/foundations/` — if this file and the code
ever disagree, the code wins; update this file to match.

## Thesis

Dealo's product is honest arithmetic — someone checked the real prices so
the shopper doesn't have to. The design leans into a receipt/ledger
aesthetic: aligned figures, tabular numbers, visible math. The bet is that
**legibility itself signals trust** — no coupon-site confetti, no fake
urgency, just numbers that add up in plain sight. This matters because the
real user is a non-technical, price-conscious shopper who is actively
skeptical of "too good to be true" savings sites — the design's job is to
read as credible and precise, not hype-y.

## Color

Defined in `react/src/theme/foundations/colors.js` as Chakra semantic
tokens (each has a light `default` and a `_dark` value; components
reference the token name, never a raw hex).

| Token | Light | Dark | Use |
|---|---|---|---|
| `bg` | `#F1F2EE` | `#121311` | Page background — cool paper, not warm cream |
| `surface` | `#FFFFFF` | `#1A1C18` | Cards |
| `surface2` | `#FBFBF9` | `#1F211B` | Secondary surfaces (e.g. card nudge) |
| `surface3` | `#EDEEE8` | `#232019` | Tertiary (icon swatches, thumbnails) |
| `border` | `#DBDCD3` | `#2C2E27` | Default borders |
| `borderStrong` | `#C7C9BC` | `#3A3D33` | Emphasized borders, connectors |
| `text` | `#12151A` | `#EFEEE8` | Primary text — near-black ink |
| `text2` | `#585F5B` | `#A5A99F` | Secondary text |
| `text3` | `#8B918C` | `#787D72` | Tertiary / muted text |
| `brand` | `#0A6B41` | `#39B57C` | Primary brand green — deep, serious |
| `brandHover` | `#084F31` | `#4FD693` | Hover/active state of brand |
| `brandSoft` | `#E4EEE6` | `#193226` | Soft brand background (icon chips, active nav) |
| `brass` | `#B9852E` | `#D9A748` | **The one deliberate rich accent** |
| `brassSoft` | `#F4E7CC` | `#2E2617` | Soft brass background |
| `danger` | `#B23A2E` | `#E0685A` | Errors |

**The brass rule:** brass is spent in exactly one place — confirmation/
verification moments (e.g. the card-visual chip in `CardFomo`). It does not
appear in general UI. This is deliberate: "spend your boldness in one
place; keep everything around it quiet."

Secondary accents (`cyan`, `amber`, `violet`) exist for specific semantic
uses (e.g. `amber` for the "Before you buy" caution box in `HowToSteps`) —
these are pre-existing, not part of the Ledger direction, and were left
unchanged.

## Typography

Defined in `react/src/theme/foundations/typography.js`. Loaded via
`react/index.html` (Google Fonts link — Hanken Grotesk 500–800, IBM Plex
Mono 400–700).

- **Hanken Grotesk** — `fonts.heading` / `fonts.body`. Warm, humanist
  grotesque for all UI text and headings. Not the "safe SaaS" Inter/Space
  Grotesk default — chosen for a friendlier character while staying
  precise.
- **IBM Plex Mono** — `fonts.mono`. Every rupee amount and percentage,
  everywhere, via `fontFamily="mono"`. Real tabular figures — this is what
  makes the "audited, not guessed" feeling work. Never use body font for a
  price.

## Shape & elevation

`react/src/theme/foundations/typography.js` (radii) and `shadows.js`.

- Radii: `xs` 8px, `sm` 12px, `md` 14px, `lg` 20px, `pill` 999px.
- Shadows are warm-neutral (`rgba(18,21,26,…)`, matching the ink color),
  never pure black. `shadows.ring` is the standard focus-visible ring
  (`Card`'s `_focusVisible`), `shadows.brand` is a soft green glow used
  sparingly, `shadows.savingsHairline` is a near-invisible 1px accent under
  `SavingsBar`.

## Component patterns

- **`SavingsBar`** — the hero. Centered, large tabular "You save ₹X"
  figure (36–46px), with the was→now price line below as supporting
  detail. This is the dominant visual element on the results page; nothing
  should compete with it in size.
- **`Journey` / `JourneyStep`** — vertical checklist (merchant → gift
  voucher → checkout), not horizontal. Each step: an outline dot that fills
  to a checkmark on click, a label + detail line, and an action button on
  the right that opens the real external link. Deliberately not sequenced
  — no artificial locking between steps. A ~550ms "Confirming…" pending
  state precedes the checkmark landing so the confirmation is noticed, not
  missed.
- **`ProductIdentity` / `ProductCandidateCard`** — when a real product
  photo is available, it gets a full-width banner treatment (`ProductIdentity`)
  or a large (76px) square thumbnail (`ProductCandidateCard`) — never a
  small icon when a real photo exists. Icon fallback only when no photo.
- **`CardFomo`** — an illustrated, generic card graphic (not a scan of any
  real bank's card — avoids reproducing bank/card-network trademarks). The
  card brand name is shown as text next to the graphic, not baked into it.

## Copy rules (plain language)

The real user is a non-technical, first-time visitor who may be skeptical
of "too good to be true" savings sites. Every string was audited against
this (see commit history on `design/ledger-implementation`):

- **"Gift Voucher"**, not "voucher" — it's the real product name and
  already a familiar, trusted concept (like a gift card). Don't invent a
  softer synonym for something people already understand.
- **Never say "route"** in user-facing copy — say "the best way to buy
  this" or similar. "Route" is internal/engineering language.
- **Never say "UPI"** standalone — it was never explained and doesn't help
  a shopper decide anything.
- **"Gyftr"** (the voucher partner's brand name) is never shown
  unexplained — link text says "our voucher partner" instead; the actual
  URL is unaffected.
- Any multi-step flow that resembles "buy a code first, then use it"
  **must** be accompanied by an explicit plain-language explanation of why
  that's safe (see the mockup's "why buy a Gift Voucher first?" pattern) —
  never leave that mechanic unexplained, it reads as a scam pattern
  otherwise.

## History

- Three directions were mocked up (Ledger / Signal / Trust Mark) as
  interactive HTML artifacts before implementation began — Ledger was
  chosen.
- Implemented across three phases on branch `design/ledger-implementation`:
  theme foundation → components (checklist, photos, logo) → copy pass.
- Not yet merged to `main` or pushed to remote as of this writing.
