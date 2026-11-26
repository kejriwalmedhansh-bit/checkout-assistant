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
// The baked body text inside #root needs nothing — createRoot replaces it,
// along with the #boot-splash logo screen that covers it while this loads.
document.querySelectorAll('script[data-prerendered]').forEach((el) => el.remove());

// Fade the app in over the splash (keyframes in index.html). Once, at boot.
document.getElementById('root').classList.add('app-in');

// A tab left open across a website update still runs the old app, and the
// old app asks for page files by their old names — which the update deleted.
// Opening another page (Store deals, About, a shop) then died with
// "Failed to fetch dynamically imported module". Vite announces that failure
// as vite:preloadError: reload once, which fetches the new app and lands on
// the page the visitor asked for. The 30-second stamp stops a reload loop if
// the file is missing for some other reason.
window.addEventListener('vite:preloadError', (event) => {
  const KEY = 'dealo:stale-reload';
  try {
    if (Date.now() - Number(sessionStorage.getItem(KEY) || 0) < 30000) return;
    sessionStorage.setItem(KEY, String(Date.now()));
  } catch {
    return; // no sessionStorage, no loop guard — leave the error as it is
  }
  event.preventDefault();
  window.location.reload();
});

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <ColorModeScript initialColorMode={theme.config.initialColorMode} />
    <ChakraProvider theme={theme}>
      <App />
    </ChakraProvider>
  </React.StrictMode>,
);
