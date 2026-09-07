import { Box, Text } from '@chakra-ui/react';

import InfoPageShell from '@/components/common/InfoPageShell';
import { usePageTitle } from '@/hooks/usePageTitle';

/**
 * The single privacy policy for all three places Dealo runs: this website,
 * the WhatsApp bot, and the Chrome extension. Deliberately one document
 * rather than three — the Chrome Web Store needs a *hosted* policy URL it
 * can point at, and three separate texts would drift apart the first time
 * one of them changed.
 *
 * Everything here was written against what the code actually does, not
 * against what a template says a policy should claim. If you change what
 * Dealo collects, this page is part of that change:
 *   - react/src/utils/analytics.js — events, the anonymous id, session replay
 *   - react/src/store/*.js         — what’s kept in the browser
 *   - src/services/analytics_service.py — WhatsApp events (keyed by phone)
 *   - src/cache.py                 — why the server keeps nothing on disk
 *   - extension/src/*.js           — what the extension sends and stores
 */
const LAST_UPDATED = 'September 7, 2026';

function Section({ title, children }) {
  return (
    <Box mb="22px">
      <Text as="h2" m="0 0 8px" fontSize="15px" fontWeight={800} letterSpacing="-.01em">
        {title}
      </Text>
      <Text as="div" fontSize="13.5px" color="text2" lineHeight={1.7}>
        {children}
      </Text>
    </Box>
  );
}

function SubHeading({ children }) {
  return (
    <Text as="h3" m="16px 0 6px" fontSize="13.5px" fontWeight={700} color="text">
      {children}
    </Text>
  );
}

/** Bulleted list, matched to the body text around it. */
function List({ children }) {
  return (
    <Box as="ul" m="0 0 0 18px" p={0} sx={{ '& li': { mb: '6px' } }}>
      {children}
    </Box>
  );
}

/**
 * A pulled-out box for the two things a reader most needs to find without
 * reading the whole page: what we never touch, and the fact that visits are
 * recorded. Burying either one in a paragraph would be the wrong call.
 *
 * The `warn` tone is amber rather than another quiet grey — the recording
 * notice is the one disclosure a reader could reasonably be surprised by, so
 * it shouldn't look like the reassuring box directly above it.
 */
function Callout({ tone = 'brand', title, children }) {
  const isWarn = tone === 'warn';
  return (
    <Box
      mb="22px"
      p="16px 18px"
      borderRadius="16px"
      border="1px solid"
      borderColor={isWarn ? 'amber' : 'border'}
      bg={isWarn ? 'amberSoft' : 'brandSoft'}
    >
      <Text m="0 0 6px" fontSize="13.5px" fontWeight={800}>
        {title}
      </Text>
      <Text as="div" m={0} fontSize="13.5px" color="text2" lineHeight={1.7}>
        {children}
      </Text>
    </Box>
  );
}

export default function PrivacyPage() {
  usePageTitle(
    'Privacy Policy',
    'Exactly what Dealo collects on the website, on WhatsApp, and in the Chrome extension — what we never collect, who else sees it, and how to have it deleted.',
  );

  return (
    <InfoPageShell title="Privacy Policy" subtitle={`Last updated ${LAST_UPDATED}`}>
      <Section title="Who this covers">
        This policy covers all three places Dealo runs: this website (getdealo.in), the Dealo bot on WhatsApp, and
        the Dealo Chrome extension. Where they differ, it says so. “We” and “us” mean Dealo (getdealo); you can
        reach us any time at the address at the bottom of this page.
      </Section>

      <Callout title="What Dealo never asks for, and never stores">
        Your card number, CVV, expiry date, OTP, UPI PIN, net-banking password, or your login for any store. There
        is no Dealo account and no Dealo password. You always pay on the store’s own website or app — your money
        never passes through us, and neither do the details behind it.
      </Callout>

      <Callout tone="warn" title="Your visits to this website are recorded">
        To see where people get stuck, we record a replay of each visit to getdealo.in — your mouse movements,
        clicks, scrolling, the pages you move through, and the text you type into the search box. It starts as soon
        as the page opens. It’s a recording of the Dealo window only: we can’t see your other tabs, and the
        recording stops at the moment you leave for a store or voucher site. These replays are held by our
        analytics provider, Mixpanel, described below.
      </Callout>

      <Section title="What we collect on the website">
        <SubHeading>What you search for</SubHeading>
        The product name you type, or the product link you paste, is sent to our server so it can run the search.
        Our server works it out and answers — it doesn’t write your search to a database. What it holds is a
        short-lived memory cache that speeds up repeat lookups and is wiped whenever the server restarts.

        <SubHeading>How you use the site</SubHeading>
        We record what happens as you use Dealo — a search being run (including the words you searched), which
        product you picked, the prices and savings you were shown, which buttons and links you tapped, and the
        replay described above. These are tied to a random identifier created by your browser on your first visit,
        not to your name.

        <SubHeading>What your browser keeps</SubHeading>
        Dealo stores a few things on your own device so the site works sensibly:
        <List>
          <li>That random identifier, so repeat visits count as one person rather than several.</li>
          <li>Your last search and its results, so a refresh or a trip to a store doesn’t lose your place.</li>
          <li>Small preferences — whether the sidebar is collapsed, whether you’ve seen the intro tour.</li>
        </List>
        Clearing your browser’s site data for getdealo.in removes all of it, and gives you a fresh identifier.

        <SubHeading>What we don’t ask for</SubHeading>
        The website has no sign-up. We never ask for your name, email address, phone number, age, or address, and
        we have no way to link a visit to you as a person unless you contact us yourself.
      </Section>

      <Section title="What we collect on WhatsApp">
        If you message the Dealo bot, WhatsApp gives us your phone number, and we receive what you send — your
        messages, and any product photo or link you share. We use them to answer you and nothing else.

        <SubHeading>How long we keep it</SubHeading>
        Your conversation is held in the server’s memory while it’s live, so the bot can remember what you were
        looking at, and is discarded after a period of inactivity or whenever the server restarts. It isn’t written
        to a database.

        <SubHeading>One thing to be aware of</SubHeading>
        Your phone number is included in the usage records we send to Mixpanel, so that the steps of one
        conversation can be read together. That means our analytics provider receives your number. We do not send
        your IP address with those records. WhatsApp messages themselves are carried by Meta, under{' '}
        <Text as="a" href="https://www.whatsapp.com/legal/privacy-policy" target="_blank" rel="noopener noreferrer" color="brand" fontWeight={700} textDecoration="underline">
          WhatsApp’s own privacy policy
        </Text>
        .
      </Section>

      <Section title="What the Chrome extension collects">
        The extension watches for a checkout or cart page, and when it sees one it asks our server a single
        question: is there a voucher for this store, and what would it save?

        <SubHeading>What it sends us</SubHeading>
        <List>
          <li>The store’s domain — <em>croma.com</em>, for example. Not the full page address, not the product, not the page’s contents.</li>
          <li>The order total shown on the page, when it can read one confidently, so the saving can be shown in rupees rather than as a percentage. If it can’t, nothing is sent for this.</li>
          <li>The full address of the page you’re on, but only at the moment you use the button that sends you back to the store through our link (see “How Dealo makes money” below).</li>
        </List>

        <SubHeading>What it keeps on your device, and never sends us</SubHeading>
        <List>
          <li>Whether you’ve already dismissed the popup for a store, so it doesn’t ask twice.</li>
          <li>A note of a purchase you’re part-way through — the store, the total, the suggested voucher — because buying a voucher means leaving the store and coming back. Discarded after seven days, or as soon as the purchase is done.</li>
          <li>Voucher codes you’ve bought, so you can paste them back into the store’s discount box. These stay on your machine. Our servers never receive them.</li>
        </List>

        <SubHeading>Why it asks to run on all websites</SubHeading>
        Chrome warns that the extension can read and change your data on all websites. It asks for that because it
        can’t know in advance which store you’ll shop at — it has to be on the page to notice you’ve reached a
        checkout. It does not read or send the contents of the pages you visit, beyond the order total described
        above. The extension has no account and no identifier: nothing it sends is tied to who you are.
      </Section>

      <Section title="Who else sees this information">
        We don’t sell your information, and we don’t share it for anyone else’s advertising. It reaches these
        companies only because they do a specific job for Dealo:
        <List>
          <li><strong>Mixpanel</strong> — our analytics provider. Holds the usage records and session replays described above, on European servers.</li>
          <li><strong>Meta (WhatsApp)</strong> — carries messages to and from the Dealo bot. WhatsApp only.</li>
          <li><strong>Search and page-reading services</strong> — receive the product name or link you searched, so they can fetch public store pages on our behalf and read the price. They receive what you searched for, not who you are.</li>
          <li><strong>Affiliate networks</strong> — see the click that sends you to a store, as described below.</li>
          <li><strong>Our hosting providers</strong> — run the website and the server, and keep short-lived technical logs of requests, as any web host does.</li>
        </List>
        We may also share information if the law requires it of us.
      </Section>

      <Section title="How Dealo makes money">
        Dealo is free. When you go to a store or voucher partner through a Dealo link, that click is routed through
        an affiliate network, and if you buy something we may earn a commission. The commission is paid by the
        store out of its own margin — it adds nothing to your price, and it isn’t what decides which route Dealo
        shows you. That’s decided by the final price you’d pay. The network sees the click and the resulting
        purchase; it doesn’t receive your identity from us.
      </Section>

      <Section title="How long things are kept">
        <List>
          <li><strong>On our server:</strong> nothing is written to disk. Searches and conversations live in memory and are gone on restart.</li>
          <li><strong>Usage records and session replays:</strong> held by Mixpanel for as long as we keep using the service, unless you ask us to delete yours.</li>
          <li><strong>On your device:</strong> until you clear your browser’s site data, or remove the extension.</li>
        </List>
      </Section>

      <Section title="Your choices">
        <List>
          <li>Clearing your site data for getdealo.in resets your identifier and removes everything the site kept on your device.</li>
          <li>Removing the extension removes everything it stored, including any saved voucher codes.</li>
          <li>You can ask us for a copy of what we hold about you, ask us to correct it, or ask us to delete it — email us and we’ll do it. For the website, tell us roughly when you visited, since we have no name to look you up by. For WhatsApp, your phone number is enough.</li>
        </List>
      </Section>

      <Section title="Children">
        Dealo isn’t intended for anyone under 18, and we don’t knowingly collect information from children. If you
        believe a child has used Dealo and sent us something, email us and we’ll delete it.
      </Section>

      <Section title="Keeping it safe">
        The site and the extension talk to our server over an encrypted connection, and access to our analytics is
        limited to the people running Dealo. No service on the internet can promise perfect security, and we won’t
        pretend otherwise — but the most sensitive thing about a purchase, the payment itself, never reaches us at
        all.
      </Section>

      <Section title="Changes to this policy">
        If what we collect changes, we’ll update this page and change the date at the top. Worth a look now and
        then if you use Dealo regularly.
      </Section>

      <Section title="Contact">
        Questions about this policy, or a request to see or delete your information? Email{' '}
        <Text as="a" href="mailto:medhansh@getdealo.in" color="brand" fontWeight={700} textDecoration="underline">
          medhansh@getdealo.in
        </Text>
        .
      </Section>
    </InfoPageShell>
  );
}
