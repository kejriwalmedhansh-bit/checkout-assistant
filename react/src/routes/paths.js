/**
 * Single source of truth for route paths. Always reference ROUTES.* instead of
 * hardcoding strings so links and redirects stay in sync.
 */
export const ROUTES = {
  home: '/',
  select: '/select',
  results: '/results',
  vouchers: '/vouchers',
  voucherDetail: '/vouchers/:slug',
};
