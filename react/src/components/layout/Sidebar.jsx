import { Box, Flex, Link, Switch, Text, Tooltip } from '@chakra-ui/react';
import { Link as RouterLink, useMatch } from 'react-router-dom';

import Eyebrow from '@/components/common/Eyebrow';
import { I } from '@/components/common/icons';
import LogoIcon from '@/components/common/LogoIcon';
import WhatsAppButton from '@/components/common/WhatsAppButton';
import { ROUTES } from '@/routes/paths';
import { useUiStore } from '@/store/uiStore';

/** Fixed icon-slot width — keeps every icon on one vertical center line. */
const ICON_SLOT = 34;

const NAV = [{ to: ROUTES.home, icon: I.search, label: 'Search', end: true }];

/**
 * Fade-only style for "collapse-hidden" elements (labels, wordmark, controls).
 * Changes opacity only — never size or layout — so icons never move. The
 * collapsing rail clips the fixed-width content for a jitter-free transition.
 */
function fade(collapsed) {
  return {
    opacity: collapsed ? 0 : 1,
    pointerEvents: collapsed ? 'none' : 'auto',
    transition: 'opacity .14s ease',
    whiteSpace: 'nowrap',
  };
}

/** Fixed-width slot that centers its icon. */
function IconSlot({ children }) {
  return (
    <Flex w={`${ICON_SLOT}px`} flex="0 0 auto" justify="center" align="center">
      {children}
    </Flex>
  );
}

function NavItem({ to, end, icon: Ico, label, onNavigate, collapsed }) {
  const active = Boolean(useMatch({ path: to, end: Boolean(end) }));
  const fx = fade(collapsed);

  return (
    <Link
      as={RouterLink}
      to={to}
      onClick={onNavigate}
      position="relative"
      display="flex"
      alignItems="center"
      w="100%"
      p="9px 0"
      pr="11px"
      borderRadius={active ? '9px' : '11px'}
      fontSize="13px"
      fontWeight={600}
      color={active ? 'brandText' : 'text2'}
      bg={active ? 'brandSoft' : 'transparent'}
      _hover={{
        textDecoration: 'none',
        bg: active ? 'brandSoft' : 'surface3',
        color: active ? 'brandText' : 'text',
      }}
    >
      {active && (
        <Box position="absolute" left="-10px" top="10px" bottom="10px" w="3px" borderRadius="99px" bg="brand" />
      )}
      <Tooltip label={label} placement="right" hasArrow openDelay={250} borderRadius="8px" isDisabled={!collapsed}>
        <IconSlot>
          <Ico size={17} />
        </IconSlot>
      </Tooltip>
      <Box as="span" flex={1} textAlign="left" sx={fx}>
        {label}
      </Box>
    </Link>
  );
}

/**
 * Inner sidebar content. A single fixed-width (264px) layout used in every state:
 * desktop expanded / collapsed (the parent clips it; labels fade here) and the
 * mobile drawer (`collapsed` is always false). `onNavigate` closes the mobile
 * drawer on nav clicks.
 */
export default function SidebarContent({ onNavigate, collapsed = false, onOpenOnboarding }) {
  const fx = fade(collapsed);
  const hintsEnabled = useUiStore((s) => s.hintsEnabled);
  const toggleHints = useUiStore((s) => s.toggleHints);

  return (
    <Flex direction="column" h="100%" w="264px" p="14px" bg="sidebar">
      {/* logo — links home from anywhere in the app. The icon lives in the
          fixed slot (always visible, even collapsed); the wordmark fades
          with the other labels rather than snapping in/out, matching how
          nav labels behave on collapse. */}
      <Flex as={RouterLink} to={ROUTES.home} align="center" gap="9px" pt="6px" pb="16px" _hover={{ textDecoration: 'none' }}>
        <LogoIcon size={26} />
        <Text as="span" sx={fx} fontSize="21px" fontWeight={800} letterSpacing="-.015em" lineHeight={1}>
          <Box as="span" color="brand">
            deal
          </Box>
          <Box as="span" color="brass">
            o
          </Box>
        </Text>
      </Flex>

      <Flex as="nav" direction="column" gap="3px" mt="18px">
        <Eyebrow pl="14px" pb="8px" sx={fx}>
          Menu
        </Eyebrow>
        {NAV.map((n) => (
          <NavItem key={n.to} {...n} onNavigate={onNavigate} collapsed={collapsed} />
        ))}
      </Flex>

      <Flex mt="auto" direction="column" gap="10px">
        <Box h="1px" bg="border" />

        <WhatsAppButton collapsed={collapsed} />

        <Box h="1px" bg="border" />

        {/* Jumps into the live guided tour at whichever step belongs to the
            current page (see AppLayout.jsx's openOnboarding) — never a
            navigation to the homepage, so it never drops an in-progress
            checkout on /select or /results. Also reachable from the mobile
            header, since the sidebar itself is hidden behind a drawer
            there. */}
        <Tooltip label="How it works" placement="right" hasArrow openDelay={250} isDisabled={!collapsed}>
          <Box
            as="button"
            type="button"
            onClick={onOpenOnboarding}
            display="flex"
            alignItems="center"
            w="100%"
            p="9px 0"
            pr="11px"
            borderRadius="11px"
            fontSize="13px"
            fontWeight={600}
            color="text2"
            _hover={{ bg: 'surface3', color: 'text' }}
          >
            <IconSlot>
              <I.info size={17} />
            </IconSlot>
            <Box as="span" flex={1} textAlign="left" sx={fx}>
              How it works
            </Box>
          </Box>
        </Tooltip>

        {/* Durable off-switch for the results-page step hints. They show on
            every visit by default, so someone who finds them repetitive needs
            a real way out — not just the per-visit "Hide" on the bubble. */}
        <Flex align="center" justify="space-between" p="4px 0" sx={fx}>
          <Text as="label" htmlFor="hints-toggle" fontSize="12px" color="text2" cursor="pointer">
            Step hints
          </Text>
          <Switch
            id="hints-toggle"
            size="sm"
            isChecked={hintsEnabled}
            onChange={toggleHints}
            aria-label="Show step-by-step hints on the results page"
          />
        </Flex>

        <Box p="4px 0" sx={fx}>
          <Text fontSize="12px" color="text3">
            The smartest way to buy
          </Text>
        </Box>
      </Flex>
    </Flex>
  );
}
