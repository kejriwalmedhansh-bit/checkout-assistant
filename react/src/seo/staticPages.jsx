/**
 * Build-time render of the text-only pages, for scripts/prerender.mjs.
 *
 * Privacy, Terms and the ChatGPT & Claude help page are read by machines
 * before any browser runs our JavaScript: OpenAI's plugin review checks the
 * privacy policy automatically, and on 2026-10-03 it reported it couldn't
 * — the raw file held only the page title. Rendering the real components
 * here, rather than keeping a hand-copied text version, means the readable
 * copy can never drift from what visitors see.
 */
import { ChakraProvider } from '@chakra-ui/react';
import { renderToStaticMarkup } from 'react-dom/server';
import { MemoryRouter } from 'react-router-dom';

import ChatAppsPage from '@/pages/ChatAppsPage';
import PrivacyPage from '@/pages/PrivacyPage';
import TermsPage from '@/pages/TermsPage';
import theme from '@/theme';

const PAGES = {
  '/privacy/': PrivacyPage,
  '/terms/': TermsPage,
  '/chatgpt-claude/': ChatAppsPage,
};

/** Plain semantic HTML for a page: headings, paragraphs, lists, links. */
export function renderStaticPage(path) {
  const Page = PAGES[path];
  if (!Page) return null;
  // Chakra uses useLayoutEffect, which React warns about on every server
  // render. Harmless here: this markup is replaced, never hydrated.
  const warn = console.error;
  console.error = (msg, ...rest) => {
    if (typeof msg === 'string' && msg.includes('useLayoutEffect does nothing on the server')) return;
    warn(msg, ...rest);
  };
  const html = renderToStaticMarkup(
    <ChakraProvider theme={theme} resetCSS={false}>
      <MemoryRouter initialEntries={[path]}>
        <Page />
      </MemoryRouter>
    </ChakraProvider>,
  );
  console.error = warn;
  // Chakra's inline <style> tags and class names mean nothing to a reader
  // and React replaces this markup on boot anyway.
  return html
    .replace(/<style[^>]*>[\s\S]*?<\/style>/g, '')
    .replace(/\s(class|style|data-[a-z-]+)="[^"]*"/g, '')
    .replace(/<button[\s\S]*?<\/button>/g, '');
}
