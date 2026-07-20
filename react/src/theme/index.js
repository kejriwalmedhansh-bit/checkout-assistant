/**
 * theme.js — the app-wide Chakra theme.
 *
 * This is the maintainable single source for design tokens and component looks.
 * Light/dark are driven by Chakra's native color mode (toggled by ThemeToggle and
 * persisted to localStorage); semantic tokens resolve per-mode so nothing else in
 * the app needs to branch on the theme.
 *
 * To re-skin the product, edit `foundations/*` — not individual components.
 */
import { extendTheme } from '@chakra-ui/react';

import { semanticColors } from './foundations/colors';
import { semanticShadows } from './foundations/shadows';
import { fonts, radii } from './foundations/typography';
import { styles } from './styles';
import { buttonTheme } from './components/button';
import { inputTheme, textareaTheme } from './components/input';
import { switchTheme } from './components/switch';

const config = {
  // Dark is the default look. Anyone who has already used ThemeToggle keeps their
  // stored choice — this only sets what a first-time visitor sees.
  //
  // Note: `ColorModeScript` in main.jsx does NOT run before first paint in this
  // client-rendered Vite app, so the pre-paint canvas colour is handled by the
  // inline style + script in index.html. Change both together.
  initialColorMode: 'dark',
  useSystemColorMode: false,
};

const theme = extendTheme({
  config,
  styles,
  fonts,
  radii,
  semanticTokens: {
    colors: semanticColors,
    shadows: semanticShadows,
  },
  components: {
    Button: buttonTheme,
    Input: inputTheme,
    Textarea: textareaTheme,
    Switch: switchTheme,
  },
});

export default theme;
