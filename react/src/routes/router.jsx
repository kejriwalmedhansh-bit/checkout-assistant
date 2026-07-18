import { createBrowserRouter, Navigate } from 'react-router-dom';

import AppLayout from '@/components/layout/AppLayout';
import SearchPage from '@/pages/SearchPage';
import ProductSelectPage from '@/pages/ProductSelectPage';
import ResultsPage from '@/pages/ResultsPage';
import { ROUTES } from './paths';

// Public dashboard — no ProtectedRoute / GuestRoute.
export const router = createBrowserRouter([
  {
    element: <AppLayout />,
    children: [
      { path: ROUTES.home, element: <SearchPage /> },
      { path: ROUTES.select, element: <ProductSelectPage /> },
      { path: ROUTES.results, element: <ResultsPage /> },
    ],
  },
  { path: '*', element: <Navigate to={ROUTES.home} replace /> },
]);
