/**
 * Short links for the places Dealo is posted: getdealo.in/ig, /wa, /rd...
 *
 * A plain address people trust to tap, that still says where the visit came
 * from. The long ?utm_source=... form does the same job but looks like a
 * tracking link, which is what it is.
 *
 *   getdealo.in/ig            Instagram -> homepage
 *   getdealo.in/ig/dominos    Instagram -> the Domino's shop page
 *   getdealo.in/ig/pvr-reel   Instagram, the "pvr-reel" post -> homepage
 *   getdealo.in/c/bhargavi    a creator named bhargavi -> homepage
 *
 * The second part is a shop page when one has that name, otherwise it is
 * just the name of the post, reel or person (the campaign). Either way it is
 * recorded, and the address bar is tidied to the page's own address, so a
 * visitor who forwards the link passes on a clean one.
 *
 * The visit is counted as utm_source=<channel>, utm_medium=short_link,
 * utm_campaign=<second part> (see currentTouch in utils/analytics.js).
 */

/** Short code -> the source name every report shows. Codes must not clash with a page in routes/paths.js. */
export const CHANNELS = {
  ig: 'instagram',
  wa: 'whatsapp',
  rd: 'reddit',
  qa: 'quora',
  in: 'linkedin',
  yt: 'youtube',
  fb: 'facebook',
  x: 'x',
  em: 'email',
  c: 'creator',
};

/**
 * Named posts, reels and creators, as "<code>/<name>". Only needed so the
 * link answers properly for link previews (WhatsApp, LinkedIn); a name that
 * is not listed still opens and is still counted. Add one line per new post.
 */
export const CAMPAIGNS = [];

const NAME = /^[a-z0-9][a-z0-9-]{0,39}$/;

/** { code, source, name } for a short-link address, else null. */
export function readShortLink(pathname) {
  const [code, name, extra] = String(pathname || '').toLowerCase().split('/').filter(Boolean);
  if (!code || extra || !Object.hasOwn(CHANNELS, code)) return null;
  if (name && !NAME.test(name)) return null;
  return { code, source: CHANNELS[code], name: name || null };
}
