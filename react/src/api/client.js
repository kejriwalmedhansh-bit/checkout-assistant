/**
 * Axios instance shared by every API module.
 *
 * Dealo's dashboard is public (no auth), so this is a minimal instance: a shared
 * baseURL + JSON headers and a plain error passthrough. Errors are surfaced to
 * callers unchanged; presentation is handled by `@/utils/errors`.
 */
import axios from 'axios';

import { API_BASE_URL } from '@/config';

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: { 'Content-Type': 'application/json' },
});

// Response passthrough — resolve on success, reject on error (no interceptors).
apiClient.interceptors.response.use(
  (response) => response,
  (error) => Promise.reject(error),
);
