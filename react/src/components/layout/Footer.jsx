import { Box, Flex, Link as ChakraLink, Text } from '@chakra-ui/react';
import { Link as RouterLink } from 'react-router-dom';

import Logo from '@/components/common/Logo';
import { ROUTES } from '@/routes/paths';

const COLUMNS = [
  {
    heading: 'Product',
    links: [
      { to: ROUTES.home, label: 'Search' },
      { to: ROUTES.brands, label: 'Store deals' },
      { to: ROUTES.howItWorks, label: 'How it works' },
    ],
  },
  {
    heading: 'Company',
    links: [
      { to: ROUTES.about, label: 'About' },
      { to: ROUTES.contact, label: 'Contact' },
    ],
  },
  {
    heading: 'Legal',
    links: [
      { to: ROUTES.privacy, label: 'Privacy' },
      { to: ROUTES.terms, label: 'Terms' },
    ],
  },
];

function FooterCol({ heading, links }) {
  return (
    <Box>
      <Text m="0 0 10px" fontFamily="mono" fontSize="11px" fontWeight={600} letterSpacing=".08em" textTransform="uppercase" color="text3">
        {heading}
      </Text>
      <Flex direction="column" gap="8px">
        {links.map((l) => (
          <ChakraLink
            key={l.to}
            as={RouterLink}
            to={l.to}
            fontSize="13px"
            color="text2"
            _hover={{ color: 'text', textDecoration: 'underline' }}
          >
            {l.label}
          </ChakraLink>
        ))}
      </Flex>
    </Box>
  );
}

/**
 * The site-wide footer — real bottom of the page, after every page's own
 * content, not tucked into the sidebar. Standard four-block layout (brand +
 * three link columns, copyright line below) so the site reads like an
 * ordinary website rather than an app shell with no floor.
 */
export default function Footer() {
  return (
    <Box as="footer" mt={{ base: '28px', md: '64px' }} borderTop="1px solid" borderColor="border">
      <Flex
        maxW="1340px"
        mx="auto"
        w="100%"
        direction={{ base: 'column', md: 'row' }}
        justify="space-between"
        gap={{ base: '32px', md: '24px' }}
        px={{ base: '16px', md: '34px' }}
        py="40px"
      >
        <Box maxW="260px">
          <Logo size={22} />
          <Text mt="10px" fontSize="12.5px" color="text3" lineHeight={1.6}>
            The cheapest legitimate way to pay, before you check out.
          </Text>
        </Box>

        <Flex gap={{ base: '28px', sm: '48px' }} wrap="wrap">
          {COLUMNS.map((c) => (
            <FooterCol key={c.heading} {...c} />
          ))}
        </Flex>
      </Flex>

      <Box borderTop="1px solid" borderColor="border">
        <Text
          maxW="1340px"
          mx="auto"
          px={{ base: '16px', md: '34px' }}
          py="18px"
          fontSize="11.5px"
          color="text3"
        >
          © {new Date().getFullYear()} getdealo. Dealo never asks for your card number or OTP.
        </Text>
      </Box>
    </Box>
  );
}
