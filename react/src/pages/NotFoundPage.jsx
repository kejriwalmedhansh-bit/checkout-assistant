import { useEffect } from 'react';
import { Box, Flex, Link as ChakraLink, Text } from '@chakra-ui/react';
import { Link as RouterLink, useLocation, useNavigate } from 'react-router-dom';

import InfoPageShell from '@/components/common/InfoPageShell';
import SearchBox from '@/components/common/SearchBox';
import { usePageTitle } from '@/hooks/usePageTitle';
import { ROUTES } from '@/routes/paths';
import { useSearchStore } from '@/store/searchStore';
import { track } from '@/utils/analytics';

/**
 * Shown for any address that isn't a real page.
 *
 * This replaces a silent redirect to the homepage. A redirect looks tidy but
 * lies to the person: they asked for something specific, landed somewhere
 * else, and were never told the address was wrong — so a typo in a shared
 * link is indistinguishable from Dealo losing their page.
 *
 * The search box is here rather than a bare "go home" link because a wrong
 * address is not a dead end: whatever they were after, searching for it is
 * the thing Dealo is actually for.
 *
 * Note this page renders under a real HTTP 404 from the host — an unknown
 * path has no file of its own, so the host answers 404 and serves index.html
 * as the body, and the router takes it from there. That's exactly right here:
 * the status line and the page now say the same thing.
 */
const LINKS = [
  { to: ROUTES.home, label: 'Search for a product' },
  { to: ROUTES.brands, label: 'Browse store deals' },
  { to: ROUTES.howItWorks, label: 'How Dealo works' },
  { to: ROUTES.contact, label: 'Contact us' },
];

export default function NotFoundPage() {
  usePageTitle('Page not found', 'That address doesn’t exist on Dealo. Search for what you were looking for, or head back to the homepage.');

  const navigate = useNavigate();
  const location = useLocation();
  const runSearch = useSearchStore((s) => s.runSearch);

  // Worth knowing which addresses people actually land on: a bad link we've
  // published somewhere shows up here as the same path over and over, where a
  // plain typo never repeats. In an effect keyed on the path, not in render —
  // otherwise StrictMode's double render and every re-render would each count
  // as another arrival.
  useEffect(() => {
    track('Page Not Found', { path: location.pathname });
  }, [location.pathname]);

  const onSubmit = (q) => {
    runSearch(q); // fire-and-forget — ProductSelectPage subscribes to the store
    navigate(ROUTES.select);
  };

  return (
    <InfoPageShell
      title="Page not found"
      subtitle="That address doesn’t exist on Dealo. It may have been mistyped, or the page may have moved since the link was made."
    >
      <Box mb="26px">
        <Text m="0 0 10px" fontSize="13.5px" color="text2" lineHeight={1.7}>
          If you were looking for something to buy, search for it here:
        </Text>
        <SearchBox size="md" onSubmit={onSubmit} buttonLabel="Search" />
      </Box>

      <Text m="0 0 10px" fontFamily="mono" fontSize="11px" fontWeight={600} letterSpacing=".08em" textTransform="uppercase" color="text3">
        Or go to
      </Text>
      <Flex direction="column" gap="8px">
        {LINKS.map((l) => (
          <ChakraLink
            key={l.to}
            as={RouterLink}
            to={l.to}
            fontSize="13.5px"
            fontWeight={700}
            color="brand"
            w="fit-content"
            _hover={{ textDecoration: 'underline' }}
          >
            {l.label}
          </ChakraLink>
        ))}
      </Flex>
    </InfoPageShell>
  );
}
