import { Box, Flex, Link, Switch, Text, Tooltip } from '@chakra-ui/react';
import { Link as RouterLink, useMatch } from 'react-router-dom';

import Eyebrow from '@/components/common/Eyebrow';
import { I } from '@/components/common/icons';
import LogoIcon from '@/components/common/LogoIcon';
import WhatsAppButton from '@/components/common/WhatsAppButton';
import { ROUTES } from '@/routes/paths';
import { useUiStore } from '@/store/uiStore';
import { track } from '@/utils/analytics';
import { botWhatsAppHref } from '@/utils/whatsappLink';

/** Fixed icon-slot width — keeps every icon on one vertical center line. */
const ICON_SLOT = 34;

const NAV = [
  { to: ROUTES.home, icon: I.search, label: 'Search', end: true },
  { to: ROUTES.brands, icon: I.store, label: 'Store deals' },
  { to: ROUTES.howItWorks, icon: I.doc, label: 'How it works', end: true },
];

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

/** Dealo-themed WhatsApp logo — classic speech bubble with tail. */
function WhatsAppIcon({ size = 17 }) {
  return (
    <Box as="svg" viewBox="0 0 24 24" w={`${size}px`} h={`${size}px`} fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 2C6.5 2 2 6.5 2 12c0 2 .6 3.8 1.5 5.3L2 22l5.3-1.5C10.2 21.4 11 22 12 22c5.5 0 10-4.5 10-10S17.5 2 12 2Z" />
    </Box>
  );
}

/** Play button — the item opens the tutorial video. */
function PlayIcon({ size = 17 }) {
  return (
    <Box as="svg" viewBox="0 0 24 24" w={`${size}px`} h={`${size}px`} fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="10" />
      <path d="M10 8.5v7l5.5-3.5L10 8.5Z" />
    </Box>
  );
}

function SidebarFooterItem({ icon: Icon, label, onClick, href, isExternal, onNavigate, collapsed }) {
  const fx = fade(collapsed);

  const content = (
    <>
      <Tooltip label={label} placement="right" hasArrow openDelay={250} isDisabled={!collapsed}>
        <IconSlot>
          <Icon />
        </IconSlot>
      </Tooltip>
      <Box as="span" flex={1} textAlign="left" sx={fx} fontSize="13px" fontWeight={600}>
        {label}
      </Box>
    </>
  );

  if (href) {
    return (
      <Link
        href={href}
        isExternal={isExternal}
        onClick={onClick}
        display="flex"
        alignItems="center"
        w="100%"
        p="9px 0"
        pr="11px"
        borderRadius="11px"
        color="text2"
        _hover={{ textDecoration: 'none', bg: 'surface3', color: 'text' }}
      >
        {content}
      </Link>
    );
  }

  return (
    <Box
      as="button"
      type="button"
      onClick={() => {
        onClick?.();
        onNavigate?.();
      }}
      display="flex"
      alignItems="center"
      w="100%"
      p="9px 0"
      pr="11px"
      borderRadius="11px"
      color="text2"
      _hover={{ bg: 'surface3', color: 'text' }}
    >
      {content}
    </Box>
  );
}

function SidebarFooter({ onNavigate, collapsed, onOpenOnboarding }) {
  const whatsappHref = botWhatsAppHref();

  return (
    <Flex direction="column" gap="3px">
      <SidebarFooterItem
        icon={WhatsAppIcon}
        label="Chat on WhatsApp"
        href={whatsappHref}
        isExternal
        onClick={() => track('Clicked WhatsApp Button', { source: 'sidebar' })}
        collapsed={collapsed}
      />
      {/* Opens the tutorial video, not the How it works page (that one is in
          the menu above) — so it’s labelled as the video, never as a second
          "How it works" that goes somewhere different. */}
      <SidebarFooterItem
        icon={PlayIcon}
        label="Watch the video"
        onClick={onOpenOnboarding}
        onNavigate={onNavigate}
        collapsed={collapsed}
      />
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
        <Box position="absolute" left="-10px" top="10px" bottom="10px" w="3px" borderRadius="999px" bg="brand" />
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

        <Box h="1px" bg="border" mt="12px" />

        <SidebarFooter onNavigate={onNavigate} collapsed={collapsed} onOpenOnboarding={onOpenOnboarding} />
      </Flex>
    </Flex>
  );
}
