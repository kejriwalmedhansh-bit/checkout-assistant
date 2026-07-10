import { createBrowserRouter, Navigate } from 'react-router-dom';

import AppLayout from '@/components/layout/AppLayout';
import SearchPage from '@/pages/SearchPage';
import ProductSelectPage from '@/pages/ProductSelectPage';
import ResultsPage from '@/pages/ResultsPage';
import VouchersPage from '@/pages/VouchersPage';
import VoucherDetailPage from '@/pages/VoucherDetailPage';
import { ROUTES } from './paths';

// Public dashboard — no ProtectedRoute / GuestRoute.
export const router = createBrowserRouter([
  {
    element: <AppLayout />,
    children: [
      { path: ROUTES.home, element: <SearchPage /> },
      { path: ROUTES.select, element: <ProductSelectPage /> },
      { path: ROUTES.results, element: <ResultsPage /> },
      { path: ROUTES.vouchers, element: <VouchersPage /> },
      { path: ROUTES.voucherDetail, element: <VoucherDetailPage /> },
    ],
  },
  { path: '*', element: <Navigate to={ROUTES.home} replace /> },
]);
