import mixpanel from 'mixpanel-browser';

const TOKEN = import.meta.env.VITE_MIXPANEL_TOKEN;
let ready = false;

if (TOKEN) {
  mixpanel.init(TOKEN, { track_pageview: false, persistence: 'localStorage' });
  ready = true;
} else if (import.meta.env.DEV) {
  // eslint-disable-next-line no-console
  console.warn('VITE_MIXPANEL_TOKEN is not set — analytics events will not be sent.');
}

/** Fire-and-forget event tracking; a no-op whenever the token isn't configured. */
export function track(event, props = {}) {
  if (!ready) return;
  mixpanel.track(event, props);
}
