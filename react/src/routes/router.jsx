import { createBrowserRouter, Navigate } from 'react-router-dom';

import AppLayout from '@/components/layout/AppLayout';
import SearchPage from '@/pages/SearchPage';
import ProductSelectPage from '@/pages/ProductSelectPage';
import ResultsPage from '@/pages/ResultsPage';
import HowItWorksPage from '@/pages/HowItWorksPage';
import BrandsIndexPage from '@/pages/BrandsIndexPage';
import BrandPage from '@/pages/BrandPage';
import AboutPage from '@/pages/AboutPage';
import ContactPage from '@/pages/ContactPage';
import PrivacyPage from '@/pages/PrivacyPage';
import TermsPage from '@/pages/TermsPage';
import { ROUTES } from './paths';

// Public dashboard — no ProtectedRoute / GuestRoute.
export const router = createBrowserRouter([
  {
    element: <AppLayout />,
    children: [
      { path: ROUTES.home, element: <SearchPage /> },
      { path: ROUTES.select, element: <ProductSelectPage /> },
      { path: ROUTES.results, element: <ResultsPage /> },
      { path: ROUTES.howItWorks, element: <HowItWorksPage /> },
      { path: ROUTES.brands, element: <BrandsIndexPage /> },
      { path: ROUTES.brand, element: <BrandPage /> },
      { path: ROUTES.about, element: <AboutPage /> },
      { path: ROUTES.contact, element: <ContactPage /> },
      { path: ROUTES.privacy, element: <PrivacyPage /> },
      { path: ROUTES.terms, element: <TermsPage /> },
    ],
  },
  { path: '*', element: <Navigate to={ROUTES.home} replace /> },
]);
