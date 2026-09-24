import { useEffect, useState } from 'react';
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
import { Link as RouterLink, Outlet, ScrollRestoration, useLocation } from 'react-router-dom';

import ConsentBanner from '@/components/common/ConsentBanner';
import FloatingWhatsAppButton from '@/components/common/FloatingWhatsAppButton';
import Logo from '@/components/common/Logo';
import { I } from '@/components/common/icons';
import TutorialVideoModal from '@/components/onboarding/TutorialVideoModal';
import { PageHeaderContext } from '@/hooks/usePageHeader';
import { ROUTES } from '@/routes/paths';
import { track, trackPageView } from '@/utils/analytics';
import { useUiStore } from '@/store/uiStore';
import Footer from './Footer';
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
  const location = useLocation();

  useEffect(() => {
    trackPageView(location.pathname);
  }, [location.pathname]);
  const collapsed = useUiStore((s) => s.sidebarCollapsed);
  const toggleSidebar = useUiStore((s) => s.toggleSidebar);
  const tutorialOpen = useUiStore((s) => s.tutorialOpen);
  const openTutorial = useUiStore((s) => s.openTutorial);
  const closeTutorial = useUiStore((s) => s.closeTutorial);
  // A page can replace the mobile bar's menu/logo/spacer slots with its own
  // controls (see usePageHeader) — null means the default shown below.
  const [pageHeader, setPageHeader] = useState(null);

  // "How it works" reopens the tutorial video popup from any page — same
  // popup a first-time visitor sees automatically on the home page (see
  // SearchPage.jsx).
  const openOnboarding = () => {
    track('Onboarding Reopened', { path: location.pathname });
    openTutorial();
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
      {/* desktop rail — always expanded on lg and up */}
      <Box
        display={{ base: 'none', lg: 'block' }}
        position="sticky"
        top={0}
        h="100dvh"
        flex="0 0 auto"
        zIndex={16}
        w="264px"
      >
        {/* clip window — full width, never collapses */}
        <Box
          position="absolute"
          inset={0}
          overflow="hidden"
          bg="sidebar"
          borderRight="1px solid"
          borderColor="border"
        >
          <SidebarContent collapsed={false} onOpenOnboarding={openOnboarding} />
        </Box>
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

      {/* Every new page opens at the top; Back returns to where you were.
          Without this, tapping a product lower down the list opened the
          results page still scrolled down, with its top hidden. */}
      <ScrollRestoration />

      {tutorialOpen && <TutorialVideoModal onClose={closeTutorial} />}

      {/* Asked once, on whichever page the visitor happens to land on, so it
          isn't tied to the homepage — a shared link to /results is somebody's
          first page just as often. */}
      <ConsentBanner />

      <FloatingWhatsAppButton />

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

        {/* Content is at least a full screen tall on its own (not just
            flex-grown to the height of its flex row, which only glues the
            footer to the bottom edge of a short page — still visible with
            no scroll). This guarantees the footer starts below the fold,
            so it only ever appears once the user actually scrolls. */}
        <Box as="main" flex={1} minW={0} w="100%">
          <Box
            minH="100dvh"
            display="flex"
            flexDirection="column"
            w="100%"
            maxW="1340px"
            mx="auto"
            p={{ base: '16px 16px 32px', md: '22px 34px 60px' }}
          >
            <PageHeaderContext.Provider value={setPageHeader}>
              <Outlet />
            </PageHeaderContext.Provider>
          </Box>

          <Footer />
        </Box>
      </Flex>
    </Flex>
  );
}
