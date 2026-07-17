# Testing Dealo — plain-language checklist

## Why this exists

Right now, Dealo has never been tested in an organized way — checking it means using it a few times and eyeballing whether the answer looks right. There's no written record of "here's what I tried, here's what it should show, here's what it actually showed." That makes it easy for something to quietly break without anyone noticing.

Also worth knowing: the project's internal notes-to-self file (the one meant to describe how the app is built and what's broken) is out of date in a couple of ways — it describes an older version of how the code is organized, and it lists two bugs that, from a quick look, seem to already be fixed. That's not something you need to act on — it's just context for why a couple of items below say "double-check this is really still broken" instead of assuming the old notes are right.

## Part 1 — How real product teams actually test things

Think of it like quality-checking a restaurant dish before it goes out to customers:

1. **Check the ingredients individually** — before cooking, you'd taste-test the sauce on its own. In software terms: check that one small calculation (like "how much does this voucher actually save you") gives the right number, by itself, before it's mixed into everything else.
2. **Check that the pieces work together** — once the dish is assembled, does it come together right? In software terms: does the app correctly combine "cheapest store," "voucher discount," and "cashback card" into one sensible final answer?
3. **Have a real person try the whole thing as a customer would** — this is the taste-tester eating the final plate. This is the most important one for Dealo right now, and it's what this checklist is for: someone actually uses the app the way a real customer would, on real products, and checks the answer makes sense.
4. **Keep an eye on it after it's live** — even after all that, spot-check it every so often once real people are using it, in case something changes upstream (a store changes its website, a voucher site changes its rules) and quietly breaks things.

Dealo today only really has a rough, undocumented version of #3. This checklist's job is to make #3 solid — written down, repeatable, with a record of what "correct" looks like — so you (or anyone helping you) can run it before every change and know right away if something broke. Turning #1 and #2 into fully automatic background checks is a separate, more technical project for later — worth doing eventually, but not needed to get a trustworthy check today.

## Part 2 — The checklist

This is meant to be run by actually using the product — no code, no technical tools needed. Each item says what to try and what you should see. Where something fails, write down what actually happened so it can be fixed.

### Before you start
- [ ] The website loads and shows the search box
- [ ] The WhatsApp number responds at all (send anything, confirm you get a reply)

### Trying real products (the core check)
- [ ] Paste a real product link from a store (Amazon, Flipkart, Myntra, Nykaa) and confirm: the price shown matches what's actually on that store's page right now
- [ ] Type a plain-text product description instead of a link (e.g. "boAt Airdopes 141") and confirm you get a sensible, matching result — not a different product that just sounds similar
- [ ] Try at least 4-5 different kinds of products (electronics, clothing, makeup, shoes) since the app behaves differently for different categories — one working example doesn't mean they all work
- [ ] Confirm the "best way to buy" shown never requires a credit card — that's supposed to always be true for the main recommendation
- [ ] Tap/click to see "other options" — confirm there are at most 3, and none of them are just the same option repeated
- [ ] If a voucher discount is shown, do the maths yourself (discount % off the price) and confirm the final price shown is actually correct
- [ ] If a cashback card is recommended, check that it's genuinely the best one available for that purchase (not just the first one listed) — worth spot-checking against the bank's own site once
- [ ] Read through everything the app shows you as a customer and confirm none of it sounds like internal jargon or confusing technical talk — it should all make sense in under 10 seconds

### Edge cases (things that should be handled gracefully, not crash)
- [ ] Paste a broken or shortened link and see what happens — it should give a sensible message, not a blank error
- [ ] Search for something obviously nonsensical (random letters) and confirm it doesn't crash or show garbage
- [ ] Search for something that's out of stock everywhere and confirm it says so clearly, rather than pretending it found a deal

### WhatsApp-specific checks
- [ ] Send a product link, then a plain-text product name, then random gibberish — confirm each gets a different, appropriate kind of reply
- [ ] When a voucher deal is part of the WhatsApp answer, confirm the discount and link actually show up correctly (this was a known problem before — worth confirming it's genuinely fixed now, live, rather than trusting old notes)
- [ ] Start a conversation, wait about 10 minutes without replying, then message again — confirm it starts fresh rather than remembering the old conversation forever

### Website-specific checks
- [ ] Click all the way through: search → see results → pick a product → see the recommended deal → see voucher details — on both a phone browser and a computer browser
- [ ] Do two searches back-to-back and confirm the second one doesn't show leftover results from the first

## What this checklist doesn't cover (a later, more technical step)

Turning this into something that checks itself automatically every time the app is changed — instead of you needing to manually run through it — is possible, but it's a separate, more technical undertaking (it involves writing extra code whose only job is to check the real code). Worth considering once this manual checklist has been run a few times and you're confident about what "correct" looks like.
