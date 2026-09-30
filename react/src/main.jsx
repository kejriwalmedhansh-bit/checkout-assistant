import React from 'react';
import ReactDOM from 'react-dom/client';
import { ChakraProvider, ColorModeScript } from '@chakra-ui/react';

import theme from '@/theme';
import App from './App';
import '@/styles/fonts.css';
import '@/styles/animations.css';

// scripts/prerender.mjs bakes each page's JSON-LD into its static HTML for
// crawlers; useJsonLd adds the live copy, so drop the baked one first or the
// page would carry two (and keep a stale one after client-side navigation).
// The baked body text inside #root needs nothing — createRoot replaces it.
document.querySelectorAll('script[data-prerendered]').forEach((el) => el.remove());

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <ColorModeScript initialColorMode={theme.config.initialColorMode} />
    <ChakraProvider theme={theme}>
      <App />
    </ChakraProvider>
  </React.StrictMode>,
);
