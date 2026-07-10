/**
 * Turn an axios/network error into a user-presentable message.
 * The backend surfaces problems as FastAPI `{ detail: "..." }`; we fall back
 * gracefully for validation arrays and network failures.
 */
export function extractErrorMessage(error, fallback = 'Something went wrong. Please try again.') {
  if (!error) return fallback;

  // Network / no response
  if (error.request && !error.response) {
    return 'Could not reach the server. Check your connection and try again.';
  }

  const detail = error.response?.data?.detail;
  if (typeof detail === 'string') return detail;

  // FastAPI validation errors come as an array of {loc, msg, ...}
  if (Array.isArray(detail) && detail.length) {
    return detail.map((d) => d.msg).filter(Boolean).join(' ') || fallback;
  }

  return error.message || fallback;
}
