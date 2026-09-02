# Dealo Chrome Extension — Privacy

_Last updated: 2026-08-31_

Dealo's Chrome extension checks whether a gift-voucher discount exists for the
store you're buying from, and tells you before you pay.

## What the extension sends to Dealo

When you're on a page that looks like a checkout or cart page, it sends two
things to Dealo's server:

1. **The store's web address** — just the domain, e.g. `croma.com`. Not the
   full page address, not the product, not the page contents.
2. **The order total shown on the page**, if it can read one — a single
   number, used only to work out the actual rupee saving. If it can't read a
   total confidently, nothing is sent for this and the extension shows a
   percentage only.

That's the whole request. It's how the extension answers one question: "does a
gift voucher exist for this store, and what would it save?"

## What the extension never sends

- Your name, email address, phone number, or any account details
- Payment or card details of any kind
- What's in your cart — item names, quantities, images
- Your browsing history, or the pages you visit outside a checkout page
- Cookies, login sessions, or anything that identifies you personally

Dealo has no account system in the extension. Nothing sent is tied to an
identity, because the extension never has one.

## Affiliate links

If no discount is available, the extension offers an "Okay" button. Clicking
it briefly routes you through Dealo's affiliate link before returning you to
the same page you were on. If you then complete the purchase, Dealo may earn a
commission from the store, at no extra cost to you. This is how Dealo is paid.
Nothing about your purchase is shared with Dealo beyond what the store's own
affiliate programme reports.

## What's stored on your device

One thing: whether you've already dismissed the popup for a given store during
your current browsing session, so it doesn't ask twice. This is cleared when
you close the browser and never leaves your computer.

## Why the extension asks to run on all websites

Chrome will warn you that the extension can "read and change all your data on
all websites." That's because it can't know in advance which store you'll shop
at — it has to be present on the page to notice you've reached a checkout. It
does not read or transmit page content beyond the order total described above.

## Contact

Questions: kejriwalmedhansh@gmail.com
