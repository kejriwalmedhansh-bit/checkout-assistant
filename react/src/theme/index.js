/**
 * theme.js — the app-wide Chakra theme.
 *
 * This is the maintainable single source for design tokens and component looks.
 * Dealo ships dark-only — the tokens in `foundations/*` are flat values, not
 * light/dark pairs, so there's nothing left to branch on.
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
  initialColorMode: 'dark',
  useSystemColorMode: false,
};

const theme = extendTheme({
  config,
  styles,
  fonts,
  radii,
  colors: semanticColors,
  shadows: semanticShadows,
  components: {
    Button: buttonTheme,
    Input: inputTheme,
    Textarea: textareaTheme,
    Switch: switchTheme,
  },
});

export default theme;
