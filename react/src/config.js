/** Runtime configuration sourced from Vite env vars (see .env / .env.example). */
export const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL?.replace(/\/$/, '') || 'http://localhost:8000';
