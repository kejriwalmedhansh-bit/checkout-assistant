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
  initialColorMode: 'light',
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
