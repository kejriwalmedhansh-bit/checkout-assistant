import { lazy, Suspense } from 'react';
import { createBrowserRouter } from 'react-router-dom';

import AppLayout from '@/components/layout/AppLayout';
import SearchPage from '@/pages/SearchPage';
import ProductSelectPage from '@/pages/ProductSelectPage';
import ResultsPage from '@/pages/ResultsPage';
import { CHANNELS } from '@/seo/shortLinks';
import { ROUTES } from './paths';

// Everything below is reached by navigating, never on first paint — code-split
// out of the main bundle (which ships eagerly) so a first-time visitor on the
// homepage isn't downloading About/Terms/brand-page code before they need it.
// Page load speed is itself a ranking signal, and the app shell (sidebar,
// footer) around each of these still renders instantly since only the Outlet
// content is lazy, not AppLayout.
const HowItWorksPage = lazy(() => import('@/pages/HowItWorksPage'));
const BrandsIndexPage = lazy(() => import('@/pages/BrandsIndexPage'));
const BrandPage = lazy(() => import('@/pages/BrandPage'));
const CategoryPage = lazy(() => import('@/pages/CategoryPage'));
const GuidePage = lazy(() => import('@/pages/GuidePage'));
const AboutPage = lazy(() => import('@/pages/AboutPage'));
const ContactPage = lazy(() => import('@/pages/ContactPage'));
const JoinCommunityPage = lazy(() => import('@/pages/JoinCommunityPage'));
const PrivacyPage = lazy(() => import('@/pages/PrivacyPage'));
const TermsPage = lazy(() => import('@/pages/TermsPage'));
const ChatAppsPage = lazy(() => import('@/pages/ChatAppsPage'));
const BuyPage = lazy(() => import('@/pages/BuyPage'));
const ShortLinkPage = lazy(() => import('@/pages/ShortLinkPage'));
const NotFoundPage = lazy(() => import('@/pages/NotFoundPage'));

function lazyPage(Component) {
  return (
    <Suspense fallback={null}>
      <Component />
    </Suspense>
  );
}

// Public dashboard — no ProtectedRoute / GuestRoute.
export const router = createBrowserRouter([
  {
    element: <AppLayout />,
    children: [
      { path: ROUTES.home, element: <SearchPage /> },
      { path: ROUTES.select, element: <ProductSelectPage /> },
      { path: ROUTES.results, element: <ResultsPage /> },
      { path: ROUTES.howItWorks, element: lazyPage(HowItWorksPage) },
      { path: ROUTES.brands, element: lazyPage(BrandsIndexPage) },
      { path: ROUTES.brand, element: lazyPage(BrandPage) },
      { path: ROUTES.category, element: lazyPage(CategoryPage) },
      { path: ROUTES.guide, element: lazyPage(GuidePage) },
      { path: ROUTES.about, element: lazyPage(AboutPage) },
      { path: ROUTES.contact, element: lazyPage(ContactPage) },
      { path: ROUTES.join, element: lazyPage(JoinCommunityPage) },
      { path: ROUTES.privacy, element: lazyPage(PrivacyPage) },
      { path: ROUTES.terms, element: lazyPage(TermsPage) },
      { path: ROUTES.chatApps, element: lazyPage(ChatAppsPage) },
      { path: ROUTES.buy, element: lazyPage(BuyPage) },

      // Short links for posts: /ig, /ig/dominos, /c/<creator> (seo/shortLinks.js).
      // Each sends the visitor on to the homepage or a shop page.
      ...Object.keys(CHANNELS).flatMap((code) => [
        { path: `/${code}`, element: lazyPage(ShortLinkPage) },
        { path: `/${code}/:name`, element: lazyPage(ShortLinkPage) },
      ]),

      // Anything else. Kept inside AppLayout so a wrong address still lands
      // in Dealo (sidebar, footer, search) rather than on a bare error page.
      // It used to redirect silently to the homepage, which told the person
      // nothing about why they weren't where they asked to be.
      { path: '*', element: lazyPage(NotFoundPage) },
    ],
  },
]);
