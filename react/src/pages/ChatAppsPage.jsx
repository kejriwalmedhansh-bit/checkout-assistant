import { Box, Text } from '@chakra-ui/react';
import { Link as RouterLink } from 'react-router-dom';

import InfoPageShell from '@/components/common/InfoPageShell';
import { usePageTitle } from '@/hooks/usePageTitle';
import { ROUTES } from '@/routes/paths';
import { PAGE_META } from '@/seo/pageMeta';

/**
 * The help page both chat-app stores ask for (Claude's "documentation URL",
 * ChatGPT's website link). Everything here mirrors src/api/routers/chat_app.py:
 * one tool, shop + amount in, gift card price out, no sign-in.
 */
const MCP_URL = 'https://mcp.getdealo.in/mcp';
const CLAUDE_ADD_URL =
  'https://claude.ai/customize/connectors?modal=add-custom-connector&connectorName=Dealo&connectorUrl=' +
  encodeURIComponent(MCP_URL);
const SUPPORT_EMAIL = 'medhansh@getdealo.in';

const EXAMPLES = [
  'I’m spending ₹4,000 on Nykaa. Cheapest way to pay?',
  'Any discount on Skechers shoes? ₹5,000',
  'Booking a ₹10,000 hotel on MakeMyTrip, how can I save?',
  'Is there a gift card offer for Tata CLiQ?',
];

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

function Steps({ children }) {
  return (
    <Box as="ol" m="0 0 0 18px" p={0} sx={{ '& li': { mb: '6px' } }}>
      {children}
    </Box>
  );
}

function A({ href, children }) {
  return (
    <Text as="a" href={href} target="_blank" rel="noopener" color="brand" fontWeight={700} textDecoration="underline">
      {children}
    </Text>
  );
}

export default function ChatAppsPage() {
  usePageTitle(PAGE_META.chatApps.title, PAGE_META.chatApps.description);

  return (
    <InfoPageShell title="Dealo in ChatGPT and Claude" subtitle="The cheapest way to pay at a shop, inside the chat.">
      <Section title="What it does">
        Tell ChatGPT or Claude which Indian shop you’re buying from, and roughly how much. Dealo checks whether
        that shop’s own gift card is sold below face value on Gyftr, Maximize or BuyHatke, and shows the
        discount, how much gift card to buy, and what you actually pay. It’s free, and there’s nothing to sign up for.
      </Section>

      <Section title="Add it to Claude">
        <Steps>
          <li>
            On a computer, signed in to Claude, open <A href={CLAUDE_ADD_URL}>this link</A>. It opens “Add custom
            connector” with Dealo filled in.
          </li>
          <li>Choose “No sign-in” if asked, then Add.</li>
          <li>In a chat, open + → Connectors and make sure Dealo is switched on.</li>
        </Steps>
        Or add it by hand: Settings → Connectors → Add custom connector, and paste{' '}
        <Text as="code" fontSize="12.5px" wordBreak="break-all">{MCP_URL}</Text>. Once added on a computer, it works in the Claude phone
        app too.
      </Section>

      <Section title="Add it to ChatGPT">
        Coming soon. Dealo will appear in ChatGPT’s plugin directory once OpenAI approves it.
      </Section>

      <Section title="Things to ask">
        <Box as="ul" m="0 0 0 18px" p={0} sx={{ '& li': { mb: '6px' } }}>
          {EXAMPLES.map((q) => (
            <li key={q}>{q}</li>
          ))}
        </Box>
        Some shops sell different cards for different things (MakeMyTrip hotels vs flights). Dealo then asks
        what you’re buying first.
      </Section>

      <Section title="What it doesn’t do yet">
        It doesn’t compare products or tell you which store sells an item cheapest, it covers online shopping
        only (not in-store vouchers), and it only knows Indian shops. Discount rates come from Dealo’s catalogue,
        which is refreshed regularly. Each answer shows the date it was last checked, and the voucher site always
        shows today’s price before you pay.
      </Section>

      <Section title="Privacy">
        When ChatGPT or Claude uses Dealo, our server receives only the shop name and the amount. It never
        receives your name, email, phone number or your conversation. Details are in our{' '}
        <Text as={RouterLink} to={ROUTES.privacy} color="brand" fontWeight={700} textDecoration="underline">
          privacy policy
        </Text>
        .
      </Section>

      <Section title="Help">
        Something not working, or a shop missing? Email{' '}
        <Text as="a" href={`mailto:${SUPPORT_EMAIL}`} color="brand" fontWeight={700} textDecoration="underline">
          {SUPPORT_EMAIL}
        </Text>
        .
      </Section>
    </InfoPageShell>
  );
}
