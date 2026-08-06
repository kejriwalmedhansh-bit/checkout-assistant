import { useState } from 'react';
import {
  Box,
  Button,
  Drawer,
  DrawerBody,
  DrawerContent,
  DrawerOverlay,
  Flex,
  Link,
  useDisclosure,
} from '@chakra-ui/react';
import { Link as RouterLink, Outlet, useLocation, useNavigate } from 'react-router-dom';

import Logo from '@/components/common/Logo';
import { I } from '@/components/common/icons';
import Spotlight from '@/components/onboarding/Spotlight';
import { TOUR_STEPS } from '@/components/onboarding/tourSteps';
import { PageHeaderContext } from '@/hooks/usePageHeader';
import { ROUTES } from '@/routes/paths';
import { track } from '@/utils/analytics';
import { useUiStore } from '@/store/uiStore';
import SidebarContent from './Sidebar';

/**
 * Public app shell.
 *  - lg and up: a sticky rail whose WIDTH animates between expanded (264px) and
 *    collapsed (76px). The rail content is a single fixed-width layout that never
 *    reflows — the rail clips it and the labels fade — so the transition is
 *    jitter-free. A floating button on the seam toggles the state.
 *  - below lg: a hamburger-triggered drawer.
 */
export default function AppLayout() {
  const drawer = useDisclosure();
  const navigate = useNavigate();
  const location = useLocation();
  const collapsed = useUiStore((s) => s.sidebarCollapsed);
  const toggleSidebar = useUiStore((s) => s.toggleSidebar);
  const startTourAtStep = useUiStore((s) => s.startTourAtStep);
  const tourActive = useUiStore((s) => s.tourActive);
  // A page can replace the mobile bar's menu/logo/spacer slots with its own
  // controls (see usePageHeader) — null means the default shown below.
  const [pageHeader, setPageHeader] = useState(null);

  // "How it works" jumps straight into the live guided tour at whichever
  // step actually belongs to the page the user is already on — never a
  // detour to the homepage. On /select it opens the picker step, on
  // /results the voucher step, and so on (see tourSteps.js's `page` field).
  // A page with no matching step (shouldn't happen given the three routes
  // above, but kept as a safety net) falls back to starting from the top.
  const openOnboarding = () => {
    const stepIndex = TOUR_STEPS.findIndex((s) => s.page === location.pathname);
    track('Onboarding Reopened', { path: location.pathname, step_index: Math.max(stepIndex, 0) });
    if (stepIndex === -1) {
      navigate(ROUTES.home);
      startTourAtStep(0);
    } else {
      startTourAtStep(stepIndex);
    }
  };

  return (
    <Flex
      // 100dvh, not 100vh -- vh is sized against the browser's largest
      // possible viewport (address bar hidden), not what's actually
      // visible. On mobile, the address bar showing/hiding during
      // ordinary scrolling shifts the real layout under a 100vh page;
      // dvh tracks the actual current viewport instead. This was a real
      // contributor to the tour ring appearing to "move around" on a
      // phone -- the underlying page itself was shifting, not the ring.
      minH="100dvh"
      bg="bg"
      bgImage="radial-gradient(circle, var(--chakra-colors-bgGrid) 1.5px, transparent 1.6px)"
      bgSize="26px 26px"
      bgPosition="-13px -13px"
    >
      {/* desktop rail */}
      <Box
        display={{ base: 'none', lg: 'block' }}
        position="sticky"
        top={0}
        h="100dvh"
        flex="0 0 auto"
        zIndex={16}
        w={collapsed ? '76px' : '264px'}
        transition="width .22s cubic-bezier(.4, 0, .2, 1)"
      >
        {/* clip window — shrinks with the rail and clips the fixed-width content */}
        <Box
          position="absolute"
          inset={0}
          overflow="hidden"
          bg="sidebar"
          borderRight="1px solid"
          borderColor="border"
        >
          <SidebarContent collapsed={collapsed} onOpenOnboarding={openOnboarding} />
        </Box>

        {/* floating collapse/expand toggle on the seam */}
        <Button
          onClick={toggleSidebar}
          aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          position="absolute"
          top="22px"
          right="-13px"
          zIndex={3}
          w="26px"
          h="26px"
          minW="26px"
          p={0}
          borderRadius="99px"
          bg="surface"
          border="1px solid"
          borderColor="borderStrong"
          boxShadow="sm"
          color="text2"
          display="grid"
          placeItems="center"
          _hover={{ bg: 'surface3', color: 'text' }}
        >
          <Box
            as="span"
            display="inline-flex"
            transform={collapsed ? 'none' : 'rotate(180deg)'}
            transition="transform .2s"
          >
            <I.chevRight size={14} />
          </Box>
        </Button>
      </Box>

      {/* mobile drawer */}
      <Drawer isOpen={drawer.isOpen} placement="left" onClose={drawer.onClose}>
        <DrawerOverlay bg="blackAlpha.600" backdropFilter="blur(2px)" />
        <DrawerContent maxW="280px" bg="sidebar">
          <DrawerBody p={0}>
            <SidebarContent
              onNavigate={drawer.onClose}
              onOpenOnboarding={() => {
                drawer.onClose();
                openOnboarding();
              }}
            />
          </DrawerBody>
        </DrawerContent>
      </Drawer>

      <Spotlight />

      <Flex direction="column" flex={1} minW={0}>
        {/* mobile top bar */}
        <Flex
          display={{ base: 'flex', lg: 'none' }}
          align="center"
          justify="space-between"
          px="16px"
          h="60px"
          position="sticky"
          top={0}
          zIndex={20}
          bg="surface"
          borderBottom="1px solid"
          borderColor="border"
        >
          {pageHeader?.left || (
            <Button
              variant="iconSubtle"
              onClick={drawer.onOpen}
              aria-label="Open menu"
              w="40px"
              h="40px"
              minW="40px"
              p={0}
              borderRadius="10px"
            >
              <I.menu size={20} />
            </Button>
          )}
          <Link as={RouterLink} to={ROUTES.home} _hover={{ textDecoration: 'none' }}>
            <Logo size={22} />
          </Link>
          {/* "How it works" lives here too, not just the sidebar drawer — on
              mobile the sidebar is hidden behind the hamburger, so this is
              the one spot guaranteed visible on every page without an
              extra tap. Sits alongside whatever page-specific control
              (back/search on results, etc.) usePageHeader supplies, rather
              than replacing it. */}
          <Flex align="center" gap="4px" flex="0 0 auto">
            <Button
              variant="iconSubtle"
              onClick={openOnboarding}
              aria-label="How it works"
              w="40px"
              h="40px"
              minW="40px"
              p={0}
              borderRadius="10px"
            >
              <I.info size={19} />
            </Button>
            {pageHeader?.right}
          </Flex>
        </Flex>

        <Box
          as="main"
          flex={1}
          minW={0}
          w="100%"
          maxW="1340px"
          mx="auto"
          p={{ base: '16px 16px 56px', md: '22px 34px 60px' }}
          // Spotlight's tour bar is fixed to the bottom of the screen — this
          // reserves matching blank space so scrolling all the way down
          // never puts real content behind it either, not just the parts
          // visible without scrolling. Note: this only guarantees clearance
          // once scrolled to the true end of a long page — a page whose
          // content is naturally short enough to end within the bar's own
          // covered strip on first paint (no scrolling yet triggered) can
          // still render underneath it there; that gap isn't closed by this
          // padding alone (2026-08-06, flagged during an audit follow-up,
          // not independently re-verified in-browser this session — check
          // an actual narrow phone/emulated viewport before trusting this
          // is fully closed).
          pb={tourActive ? { base: '190px', md: '110px' } : undefined}
          transition="padding-bottom .2s ease"
        >
          <PageHeaderContext.Provider value={setPageHeader}>
            <Outlet />
          </PageHeaderContext.Provider>
        </Box>
      </Flex>
    </Flex>
  );
}
