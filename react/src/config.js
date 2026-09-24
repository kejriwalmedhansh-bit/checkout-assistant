/** Runtime configuration sourced from Vite env vars (see .env / .env.example). */
export const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL?.replace(/\/$/, '') || 'http://localhost:8000';

/**
 * Mixpanel project token. Hardcoded deliberately: a project token is a public,
 * write-only identifier that ships in the client bundle either way, so an env
 * var buys no secrecy. It is not the API secret — never put that here.
 */
export const MIXPANEL_TOKEN = '5dcefbba60138d48545e132490cd1e4d';

/**
 * The invite link for Dealo's free WhatsApp community ("Ask Dealo — Best
 * Price Help"), where members send whatever they're about to buy and get
 * the cheapest way to pay for it.
 */
export const WHATSAPP_COMMUNITY_LINK = 'https://chat.whatsapp.com/IEbXBuUEuTv7E5FKS7x4Wt?s=cl&p=i&mlu=4';
