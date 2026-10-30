# Reading the 30-day sprint numbers in Mixpanel

Three numbers to read on day 30 (28 Nov 2026), and exactly where each one lives.
Everything below is in the Mixpanel project **DealO**. Always add the filter
**is_internal_tester is not true** so our own testing is left out.

## 1. Vouchers bought through Dealo, by seller

- Event: **Voucher Sold** (sent by our server when Hubble or Maximize confirms an order; one per order, repeats are ignored).
- Break it down by **seller** (`hubble` or `maximize`).
- Filter **seller_environment = production** so sandbox test orders are left out.
- Useful extras on the same event: **amount** (voucher value), **discount** (rupees saved), **brand** (which shop), **buyer_key** (count "unique" on it for distinct buyers).

## 2. Real users per channel

- Event: **Session Started**, counted as unique users, broken down by **surface** (`web`, `whatsapp`, `extension`).
- Most website visitors do not accept cookies, so Mixpanel cannot tell them apart; for the website, read the **total** count of Session Started as "visits", not the unique count. WhatsApp uniques are exact.

## 3. Returning users per week

- Report: **Retention**, with "Session Started" as both the first and the returning event, weekly buckets, 29 Oct to 28 Nov.
- Or an Insights report on **Session Started** with filter **is_returning_visitor = true**, grouped by week and by surface.

## The buy funnel, one per seller

Build a Funnels report with these five steps, in this order, then add a breakdown (or filter) on **seller**:

1. **Dealo Voucher Shown** — our Buy voucher offer appeared on screen
2. **Buy Voucher Tapped** — the shopper tapped Buy voucher
3. **Hubble Store Opened** — the seller's payment screen opened (the name says Hubble, but `seller` says who it really was)
4. **Hubble Payment Success** — payment went through (same note on the name)
5. **Voucher Ready** — the voucher was shown to the shopper

Every step carries the same facts: **seller**, **merchant** (shop), **amount**, **discount_pct** (our rate), **best_pct** (the public rate we beat or matched), **surface** (`journey` = cart result, `shop_card` = shop-name search, `choice_chip` = the what-are-you-buying picker; the chip only counts in step 1, so filter it out when measuring the funnel).

Why people drop out between steps 3 and 4, also by seller:

- **Store Closed Without Payment** — they closed the payment screen (`closed_by` says whether it was our button or the seller's)
- **Store Open Failed** — the payment screen could not open (`reason`)
- **Hubble Payment Failed** / **Hubble Voucher Failed** — Hubble only

Step 5 is what the website sees; **Voucher Sold** (number 1 above) is what the seller confirmed. On a healthy day the two agree.
