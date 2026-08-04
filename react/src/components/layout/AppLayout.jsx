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
import { Link as RouterLink, Outlet, useNavigate } from 'react-router-dom';

import Logo from '@/components/common/Logo';
import { I } from '@/components/common/icons';
import Spotlight from '@/components/onboarding/Spotlight';
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
  const collapsed = useUiStore((s) => s.sidebarCollapsed);
  const toggleSidebar = useUiStore((s) => s.toggleSidebar);
  const startTour = useUiStore((s) => s.startTour);
  // A page can replace the mobile bar's menu/logo/spacer slots with its own
  // controls (see usePageHeader) — null means the default shown below.
  const [pageHeader, setPageHeader] = useState(null);

  // First-visit auto-start lives on SearchPage itself, not here — the tour's
  // first step targets the search box, so it only makes sense to start once
  // that page is actually on screen (see SearchPage.jsx). This handler is
  // just the manual replay from the sidebar's "How it works" link, which
  // sends the user back to the search page and re-arms the tour from step 1
  // — a live tour can't "replay" in place the way the old screenshot modal
  // could, since each step is tied to a real action on a real page.
  const openOnboarding = () => {
    track('Onboarding Reopened From Sidebar');
    navigate(ROUTES.home);
    startTour();
  };

  return (
    <Flex
      minH="100vh"
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
        h="100vh"
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
          {pageHeader?.right || (
            // spacer matching the menu button's width, keeping the logo
            // visually centered now that there's no theme toggle to balance it
            <Box w="40px" h="40px" flex="0 0 auto" />
          )}
        </Flex>

        <Box
          as="main"
          flex={1}
          minW={0}
          w="100%"
          maxW="1340px"
          mx="auto"
          p={{ base: '16px 16px 56px', md: '22px 34px 60px' }}
        >
          <PageHeaderContext.Provider value={setPageHeader}>
            <Outlet />
          </PageHeaderContext.Provider>
        </Box>
      </Flex>
    </Flex>
  );
}
