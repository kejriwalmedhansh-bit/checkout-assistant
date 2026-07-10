import { Button, useColorMode } from '@chakra-ui/react';

import { I } from './icons';

/**
 * Light/dark toggle. Backed by Chakra's color mode (persisted to localStorage),
 * so a single click re-themes the whole app via the semantic tokens in theme.js.
 */
export default function ThemeToggle({ size = 42, variant = 'ghost', borderRadius = '99px', ...props }) {
  const { colorMode, toggleColorMode } = useColorMode();
  const Icon = colorMode === 'dark' ? I.sun : I.moon;

  return (
    <Button
      variant={variant}
      onClick={toggleColorMode}
      aria-label={`Switch to ${colorMode === 'dark' ? 'light' : 'dark'} mode`}
      w={`${size}px`}
      h={`${size}px`}
      minW={`${size}px`}
      p={0}
      borderRadius={borderRadius}
      display="grid"
      placeItems="center"
      {...props}
    >
      <Icon size={Math.round(size * 0.45)} />
    </Button>
  );
}
