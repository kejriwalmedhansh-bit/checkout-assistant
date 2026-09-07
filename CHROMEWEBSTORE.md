# Chrome Web Store Listing — Dealo

> Last Updated: 2026-09-07
> Status: **not yet submitted** — one blocker left, see "What still stands between you and submitting" at the bottom. The privacy policy is hosted and the Render sleep problem is gone.

## Store Listing

**Extension Name**
Dealo — Save at Checkout

**Short Description** (97 chars)
Checks the store you're buying from for a gift-voucher discount, and tells you before you pay.

**Detailed Description**

Dealo tells you when the order you're about to place could cost less.

Plenty of Indian stores sell their own gift vouchers at a discount — buy ₹5,000 of Myntra credit for ₹4,735, then spend it on the order you were placing anyway. The saving is real and it is offered by the store itself, but almost nobody knows it exists at the moment it matters, which is the moment before you pay.

Dealo watches for that moment. When you reach a cart or checkout page at a store Dealo covers, it works out what a voucher would actually save you on this specific order — in rupees, not a vague percentage — and shows you a small panel with the figure. If the saving isn't worth the effort, Dealo stays quiet rather than interrupting you for ₹40.

If you decide it's worth it, Dealo walks you through the rest: which voucher to buy and for how much, where to buy it, and then, when you come back to the store, it hands you the code ready to paste into the discount box. If the deal needs several vouchers, it keeps track of each one so you don't lose your place. It remembers what you were buying while you're away, because that trip crosses two websites and several pages.

Dealo never completes a purchase for you. Every payment is yours to make.

On privacy: Dealo has no accounts and no login. When you reach a checkout it sends two things to its server — the store's domain, such as croma.com, and the order total shown on the page. That's all, and it isn't tied to any identity, because Dealo doesn't have one for you. It never sends your name, your card details, or what's in your cart. Voucher codes you buy stay on your own computer and are never transmitted.

Dealo earns affiliate commission from stores when you shop through it, at no extra cost to you. That is how it is paid, and it is the only way it is paid.

Questions or problems: kejriwalmedhansh@gmail.com

**Category**
Shopping

**Single Purpose**
Tells the shopper whether a gift voucher would make the order they are currently checking out cheaper, and helps them buy and redeem it.

**Primary Language**
English

## Graphics & Assets

| Asset | Dimensions | Status | Filename |
|-------|-----------|--------|----------|
| Store Icon [REQUIRED] | 128×128 PNG | ✅ Ready | `extension/icons/icon128.png` |
| Screenshot 1 [REQUIRED] | 1280×800 | ✅ Ready | `store-assets/screenshot-1-the-moment.png` |
| Screenshot 2 [RECOMMENDED] | 1280×800 | ✅ Ready | `store-assets/screenshot-2-which-voucher.png` |
| Screenshot 3 [RECOMMENDED] | 1280×800 | ✅ Ready | `store-assets/screenshot-3-code-stays-local.png` |
| Small Promo Tile [RECOMMENDED] | 440×280 | ✅ Ready | `store-assets/promo-tile-440x280.png` |

### Screenshot Notes

**Shot 2026-09-07, all against live pages — no mockups.** In upload order:

1. `screenshot-1-the-moment.png` — a real boAt cart holding ₹7,134 of stock,
   with Dealo showing **₹350 saved on this order at Boat** and the
   voucher → pay → done strip. The product in one image.
2. `screenshot-2-which-voucher.png` — Dealo on maximize.money, ringing the
   ₹5,000 button with "1/2 · Tap ₹5,000" and stating UPI 7% ✓ against
   Card 5.1% ✗. This is the answer to "and then what do I do?".
3. `screenshot-3-code-stays-local.png` — "Paste your voucher code", with the
   words *Stays on your device* under the button. Worth including precisely
   because the all-sites permission will make a reviewer look for where the
   data goes.

Each was padded to 16:10 on the brand cream rather than cropped, so nothing
in the frame was cut to hit 1280×800.

**The fourth shot named below is still missing**, and it is the one that needs
a real purchase: the code card back on the store page, ready to paste into the
discount box. There is no honest way to stage it without buying a voucher.
Shoot it the next time you actually buy one.

Original guidance, still worth following if these are ever re-shot:

Take these against a real checkout page — reviewers can tell a mockup, and a real one is more persuasive anyway. The four that tell the story:

1. **The moment.** A real cart page with the Dealo panel showing a rupee saving. This is the whole product in one image.
2. **The instruction.** The screen telling the shopper which voucher to buy and for how much.
3. **The payoff.** The code card back on the store page, ready to copy into the discount box.
4. **Restraint.** Optional but good: a checkout where Dealo found nothing and says so plainly. It shows the extension isn't spam.

Do not put a phone frame around any of these — Dealo is desktop Chrome only, and mockups on unsupported devices are a documented rejection reason.

## Permissions Justification

Copy each cell verbatim into the matching field in the Developer Dashboard.

| Permission | Type | Justification |
|------------|------|---------------|
| `storage` | permissions | Buying a gift voucher takes the shopper away from the store to a different website and back again, across several page loads. The extension stores what the shopper was buying, the order total, and which voucher was suggested, so it can resume where it left off when they return. It also stores the voucher codes they purchase, locally, so they can be pasted into the store's discount box. None of this is transmitted anywhere; it is read only by this extension on this machine, and is deleted when the purchase completes or after seven days. |
| `http://*/*`, `https://*/*` | host_permissions | The extension has to be present on the shopper's checkout page to detect that they have reached one, and it cannot know in advance which of roughly 900 supported stores they will shop at. Host access serves two functions: the extension reads the order total from the checkout page in order to state the saving in rupees, and the background service worker is notified when a tab's address changes, so it can re-check when a store opens its cart without a full page reload. It also covers requests to the extension's own backend at dealo-backend.onrender.com. No page content beyond the store domain and the order total ever leaves the device. |

**Note on the breadth of host access.** This will draw reviewer attention and it is worth pre-empting in the submission notes. `activeTab` was considered and rejected: it grants access only on a direct click of the extension icon, and the entire value of the extension is that it warns the shopper *before* they pay without being asked. A fixed allowlist of store domains was also considered and rejected: Dealo covers roughly 1,500 brand listings across three voucher platforms, of which only 242 currently have a confirmed domain mapping, so an allowlist would silently disable the extension for most of its own catalogue.

## Privacy & Data Use

### Data Collection

**Does the extension collect user data?** Yes — two fields, described below.

| Data Type | Collected? | Transmitted Off-Device? | Purpose | Shared with Third Parties? |
|-----------|-----------|------------------------|---------|---------------------------|
| Personally identifiable info | No | No | — | No |
| Health info | No | No | — | No |
| Financial info | No | No | Payment and card details are never read or transmitted. The order total is transmitted and is disclosed under "Website content" below. | No |
| Authentication info | No | No | — | No |
| Personal communications | No | No | — | No |
| Location | No | No | — | No |
| Web history | No | No | Pages are inspected locally to detect a checkout, but no browsing history is recorded or transmitted. | No |
| User activity | No | No | — | No |
| Website content | **Yes** | **Yes** | Two values only: the store's domain (e.g. `croma.com`) and the order total displayed on the checkout page. Both are needed to determine whether a voucher exists for that store and what it would save on this order. Not tied to any identity — the extension has no accounts. | No |

### Data Use Certification

- [x] Data is NOT sold to third parties
- [x] Data is NOT used for purposes unrelated to the extension's core functionality
- [x] Data is NOT used for creditworthiness or lending purposes

## Privacy Policy

**Privacy Policy URL** — ✅ hosted, verified loading 2026-09-07:

    https://kejriwalmedhansh-bit.github.io/checkout-assistant/privacy.html

Served by GitHub Pages straight from `docs/` on `main`, no build step. The
source is `docs/privacy.html`, word-for-word the same as `extension/PRIVACY.md`.
**Change the two together** — the hosted text must keep matching the disclosure
table above, and today it does: both say the same two fields leave the device,
and both say voucher codes never do.

## Distribution

**Visibility**: Public
**Regions**: India (the vouchers, stores, and rupee amounts are India-specific; a shopper elsewhere would install it and never see a deal)

## Developer Info

**Publisher Name**: _to fill in — the name that appears publicly under the listing_
**Contact Email**: kejriwalmedhansh@gmail.com
**Support URL / Email**: kejriwalmedhansh@gmail.com
**Homepage URL**: _optional_

## Version History

| Version | Date | Changes | Status |
|---------|------|---------|--------|
| 0.1.0 | — | First submission. Package built and verified 2026-09-07 as `dealo-v0.1.0.zip` (188 KB, 17 files, `manifest.json` at the root). Checkout detection, rupee saving figure, guided voucher purchase, multi-voucher code handling, final place-order step. | Draft |

## Review Notes

### Known Issues / Limitations

- Desktop Chrome only.
- India only in practice — all covered stores and vouchers are Indian.
- The extension deliberately stays silent when the saving is under ₹500 *and* under 3%, so a reviewer testing a small basket may see nothing happen. Worth stating in the submission notes so it isn't mistaken for a broken extension. Suggest to the reviewer a test case that reliably fires. Verified live 2026-09-07: a boAt (`boat-lifestyle.com`) cart returns 7%, the widest margin of the three and the one least likely to drift below the bar; Myntra at ₹5,000 returns 4.26% and Croma 3%. Re-check these before submitting — they move with the fortnightly voucher refresh, and the 5.29% Myntra figure quoted here previously had already gone stale.
- ~~Render free-tier sleep~~ — **resolved 2026-09-07.** This was flagged as the single most likely cause of a "doesn't work" rejection: a reviewer hitting a sleeping backend would see no panel at all. The backend is now on Render's paid always-on tier, and a cold `/voucher-check` answered in 0.6s when checked. Nothing to do here before submitting.

### Rejection History

_None yet._

---

## What still stands between you and submitting

**All three original blockers are cleared as of 2026-09-07.** Kept here struck
through rather than deleted, so that a rejection can be traced back to what was
actually done:

1. ~~Register as a Chrome Web Store developer~~ — **done.** The US$5 fee is
   paid and the developer account is live.
2. ~~Take at least one screenshot~~ — **done 2026-09-07.** Three at 1280×800
   plus the promo tile, in `store-assets/`. See "Screenshot Notes" above for
   what each one shows and for the fourth shot that is still missing.

Nothing is blocking submission any more. Before you upload:

3. ~~Build the ZIP from `extension/` only~~ — **done 2026-09-07**, and checked rather than assumed: `dealo-v0.1.0.zip` at the repo root, 188 KB, 17 files, `manifest.json` at the top level, no `.git/`, no scrape data, no `PRIVACY.md`. Rebuild it with the command below after any change to `extension/`.

### Building the upload package

    cd ~/checkout-assistant/extension
    zip -r ../dealo-v0.1.0.zip . -x "*.DS_Store" "*/.impeccable/*"

Check before uploading that `manifest.json` sits at the root of the ZIP rather than inside a folder — a nested manifest is the most common upload failure:

    unzip -l ../dealo-v0.1.0.zip | grep manifest.json
