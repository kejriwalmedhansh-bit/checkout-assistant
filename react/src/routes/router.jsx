import { lazy, Suspense } from 'react';
import { createBrowserRouter, Navigate } from 'react-router-dom';

import AppLayout from '@/components/layout/AppLayout';
import SearchPage from '@/pages/SearchPage';
import ProductSelectPage from '@/pages/ProductSelectPage';
import ResultsPage from '@/pages/ResultsPage';
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
const AboutPage = lazy(() => import('@/pages/AboutPage'));
const ContactPage = lazy(() => import('@/pages/ContactPage'));
const PrivacyPage = lazy(() => import('@/pages/PrivacyPage'));
const TermsPage = lazy(() => import('@/pages/TermsPage'));

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
      { path: ROUTES.about, element: lazyPage(AboutPage) },
      { path: ROUTES.contact, element: lazyPage(ContactPage) },
      { path: ROUTES.privacy, element: lazyPage(PrivacyPage) },
      { path: ROUTES.terms, element: lazyPage(TermsPage) },
    ],
  },
  { path: '*', element: <Navigate to={ROUTES.home} replace /> },
]);
