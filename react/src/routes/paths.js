/**
 * Single source of truth for route paths. Always reference ROUTES.* instead of
 * hardcoding strings so links and redirects stay in sync.
 */
export const ROUTES = {
  home: '/',
  select: '/select',
  results: '/results',
  howItWorks: '/how-it-works',
  brands: '/brands',
  brand: '/brands/:slug',
  brandFor: (slug) => `/brands/${slug}`,
  // Shop pages grouped by kind of shop (food, fashion…), see src/seo/categories.js.
  category: '/gift-cards/:slug',
  categoryFor: (slug) => `/gift-cards/${slug}`,
  // Plain-language guides, see src/seo/guides.js.
  guide: '/guides/:slug',
  guideFor: (slug) => `/guides/${slug}`,
  // Buy a voucher inside Dealo. The address every other surface sends people to.
  buy: '/buy/:slug',
  buyFor: (slug) => `/buy/${slug}`,
  about: '/about',
  contact: '/contact',
  join: '/join',
  privacy: '/privacy',
  terms: '/terms',
  chatApps: '/chatgpt-claude',
};
