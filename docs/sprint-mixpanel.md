# Reading the Hubble buy numbers in Mixpanel

Everything below is in the Mixpanel project **DealO**. (The project is at its saved-report limit, so save each report below only after deleting an old one.) Always add the filter
**is_internal_tester is not true** so our own testing is left out, and
**environment = production** so local builds are left out.

## 1. Vouchers bought through Dealo

- Event: **Voucher Sold**. Our server sends it when Hubble confirms an order;
  one per order, repeats are ignored. This is the number the sprint is judged on.
- Filter **seller_environment = production** so Hubble sandbox orders are left out.
- Useful extras on the same event: **amount** (voucher value), **discount**
  (rupees saved), **brand** (which shop), **src** (which link brought the buyer:
  wa, ext, chat, link, or empty when they searched on the site), **buyer_key**
  (count "unique" on it for distinct buyers).

## 2. The buy funnel

Build a Funnels report with these five steps, in this order:

1. **Dealo Voucher Shown**: our Buy voucher offer appeared on screen
2. **Buy Voucher Tapped**: the shopper tapped Buy voucher
3. **Hubble Store Opened**: Hubble's payment screen opened
4. **Hubble Payment Success**: payment went through
5. **Voucher Ready**: the voucher was shown to the shopper

Every step carries the same facts: **merchant** (shop), **amount**,
**discount_pct** (our rate), **best_pct** (the public rate we beat or matched),
**placement** (journey = cart result, shop_card = shop-name search or a buy
link), **src** (the buy link's source, if any).

Most visitors never answer the cookie banner. These steps are still counted
for them, under one shared "anonymous" id, so the funnel's step totals are
right but Mixpanel cannot follow one anonymous person from step to step.
Read the funnel as totals per step, not as a conversion rate per person,
unless you filter to **consent = granted**.

Why people drop out between steps 3 and 4:

- **Store Closed Without Payment**: they closed the payment screen
  (**closed_by** says whether it was our button or Hubble's)
- **Store Open Failed**: the payment screen could not open (**reason**)
- **Hubble Payment Failed** / **Hubble Voucher Failed**

Step 5 is what the website sees; **Voucher Sold** (number 1) is what Hubble
confirmed. On a healthy day the two agree.

## 3. Which channel brought the buyers

- **Buy Link Opened**, broken down by **src**: arrivals from WhatsApp (wa),
  the extension (ext), the Claude/ChatGPT apps (chat) and shared links (link).
- **Voucher Sold**, broken down by **src**: which of those arrivals bought.
- **Voucher Sold**, broken down by **referrer_domain** and **landing_page**: the
  site that sent the buyer (www.google.com, l.instagram.com, direct) and the first
  page they landed on (for example /brands/dominos/). The same two are on every
  buy step (Dealo Voucher Shown, Buy Voucher Tapped, Hubble Store Opened...).
- For links we hand to creators or communities, add `?src=<name>` to the buy
  link (for example `getdealo.in/buy/zomato?src=desidime`). The name shows up
  on both events above.

## 4. Real users and returning users

- **Session Started**, counted as unique users, broken down by **surface**
  (web, whatsapp, extension). Most website visitors do not accept cookies, so
  for the website read the **total** count as "visits", not the unique count.
- Returning: Insights on **Session Started** with filter
  **is_returning_visitor = true**, grouped by week.

## Short links and buyer source (24 Nov 2026)

- Short links for posts: `getdealo.in/ig`, `/wa`, `/rd`, `/qa`, `/in`, `/yt`, `/fb`, `/x`, `/em`, `/c/<creator>`. A second part (`/ig/dominos`, `/ig/pvr-reel`) opens that shop page when one has the name, otherwise the homepage, and is recorded as the campaign. Defined in `react/src/seo/shortLinks.js`.
- They arrive in Mixpanel as `utm_source=<channel>`, `utm_medium=short_link`, `utm_campaign=<second part>`, on Session Started and on every buy step and Voucher Sold.
- Campaign tags are removed from the address bar after they are read, so a forwarded link is clean.
- Supabase: `buyers.first_utm_source / first_utm_campaign / first_referrer_domain / first_landing_page` (written once, at first login) and the same four without `first_` on `purchases`. `buyers.heard_from` is the buyer's own one-tap answer (event: Heard From Answered).
- www.getdealo.in counts as production from 24 Nov (PR #165). Before that, ChatGPT visits (which use www) sit under environment=development: read them with `utm_source = chatgpt.com` and no environment filter.
