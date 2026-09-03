# Chrome Web Store Listing — Dealo

> Last Updated: 2026-09-04
> Status: **not yet submitted** — three blockers remain, see "What still stands between you and submitting" at the bottom.

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
| Screenshot 1 [REQUIRED] | 1280×800 | ⬜ Not created | |
| Screenshot 2 [RECOMMENDED] | 1280×800 | ⬜ Not created | |
| Screenshot 3 [RECOMMENDED] | 1280×800 | ⬜ Not created | |
| Small Promo Tile [RECOMMENDED] | 440×280 | ⬜ Not created | |

### Screenshot Notes

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

**Privacy Policy URL** — ⚠️ **BLOCKER: not yet hosted.**

The policy text itself is written and accurate, at `extension/PRIVACY.md`. It needs to live at a public URL that loads in a browser. Cheapest route: turn on GitHub Pages for the repo and link the rendered page. A Notion page works too.

The hosted text must stay consistent with the disclosure table above. It currently is — both say the same two fields leave the device, and both say voucher codes never do.

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
| 0.1.0 | — | First submission. Checkout detection, rupee saving figure, guided voucher purchase, multi-voucher code handling, final place-order step. | Draft |

## Review Notes

### Known Issues / Limitations

- Desktop Chrome only.
- India only in practice — all covered stores and vouchers are Indian.
- The extension deliberately stays silent when the saving is under ₹500 *and* under 3%, so a reviewer testing a small basket may see nothing happen. Worth stating in the submission notes so it isn't mistaken for a broken extension. Suggest to the reviewer a test case that reliably fires: a Myntra cart of ₹5,000, which returns a 5.29% saving.
- The backend is hosted on Render's free tier, which sleeps when idle. The first request after a quiet period can take several seconds to wake, during which the extension shows nothing. If a reviewer tests once, cold, they may see no panel at all. **Consider paying for an always-on instance before submitting** — this is the single most likely cause of a "doesn't work" rejection.

### Rejection History

_None yet._

---

## What still stands between you and submitting

In the order they block you:

1. **Register as a Chrome Web Store developer** — one-time US$5 fee to Google, paid at the Developer Dashboard. Nothing can be uploaded until this clears. Do this first; it is the only step with an external dependency.
2. **Host the privacy policy** at a public URL and paste it into the listing. Required field; submission is impossible without it.
3. **Take at least one screenshot** at 1280×800. One is the minimum, three or four is much better.

Then, before you upload:

4. **Consider the Render free-tier sleep problem** described under Known Issues. A reviewer hitting a cold backend sees a dead extension.
5. **Build the ZIP from `extension/` only** — not the repository root. The package must contain `manifest.json` at its top level, and must not contain `.git/`, this file, or the scrape data.

### Building the upload package

    cd ~/checkout-assistant/extension
    zip -r ../dealo-v0.1.0.zip . -x "*.DS_Store" "*/.impeccable/*"

Check before uploading that `manifest.json` sits at the root of the ZIP rather than inside a folder — a nested manifest is the most common upload failure.
