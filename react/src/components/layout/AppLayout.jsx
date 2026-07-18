import {
  Box,
  Button,
  Drawer,
  DrawerBody,
  DrawerContent,
  DrawerOverlay,
  Flex,
  useDisclosure,
} from '@chakra-ui/react';
import { Outlet } from 'react-router-dom';

import Logo from '@/components/common/Logo';
import ThemeToggle from '@/components/common/ThemeToggle';
import { I } from '@/components/common/icons';
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
  const collapsed = useUiStore((s) => s.sidebarCollapsed);
  const toggleSidebar = useUiStore((s) => s.toggleSidebar);

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
          <SidebarContent collapsed={collapsed} />
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
            <SidebarContent onNavigate={drawer.onClose} />
          </DrawerBody>
        </DrawerContent>
      </Drawer>

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
          <Logo size={22} />
          <ThemeToggle size={40} variant="iconSubtle" borderRadius="10px" />
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
          <Outlet />
        </Box>
      </Flex>
    </Flex>
  );
}
