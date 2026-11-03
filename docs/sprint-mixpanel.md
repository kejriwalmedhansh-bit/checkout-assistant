# Reading the Hubble buy numbers in Mixpanel

Everything below is in the Mixpanel project **DealO**. Always add the filter
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
- For links we hand to creators or communities, add `?src=<name>` to the buy
  link (for example `getdealo.in/buy/zomato?src=desidime`). The name shows up
  on both events above.

## 4. Real users and returning users

- **Session Started**, counted as unique users, broken down by **surface**
  (web, whatsapp, extension). Most website visitors do not accept cookies, so
  for the website read the **total** count as "visits", not the unique count.
- Returning: Insights on **Session Started** with filter
  **is_returning_visitor = true**, grouped by week.
