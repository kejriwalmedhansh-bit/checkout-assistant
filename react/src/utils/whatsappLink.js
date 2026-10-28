import { getDealoId } from '@/utils/analytics';

// Dealo's WhatsApp bot (+91 98744 00045), digits-only as wa.me requires.
export const BOT_WHATSAPP_NUMBER = '919874400045';

// The bot recognises this exact greeting (WEBSITE_GREETINGS in
// src/services/whatsapp_service.py) — change both together.
const BOT_GREETING = "Hi! I'd like to try Dealo on WhatsApp.";

/** A uuid shrinks to ~25 characters as base36; other ids travel as-is. */
function refCode(id) {
  const hex = id.replace(/-/g, '');
  return /^[0-9a-f]{32}$/i.test(hex) ? BigInt(`0x${hex}`).toString(36) : id;
}

/**
 * wa.me link to the bot. For a visitor who agreed to be recorded, the
 * pre-filled message ends with "(ref <code>)": the bot reads it, hides it
 * from the conversation, and joins this website visitor to the WhatsApp
 * person in Mixpanel.
 *
 * `message` replaces the greeting — "Send this to my WhatsApp" pre-fills the
 * product itself, so the bot's first reply is that product's prices.
 */
export function botWhatsAppHref(message = BOT_GREETING) {
  const id = getDealoId();
  const text = id ? `${message} (ref ${refCode(id)})` : message;
  return `https://wa.me/${BOT_WHATSAPP_NUMBER}?text=${encodeURIComponent(text)}`;
}

// Links are built when a component renders, which can be before the visitor
// answers the consent banner. Rebuilding at the moment of the click means the
// code reflects their answer at that moment. Runs before the browser follows
// the link (capture phase). A link carrying its own message keeps it in
// data-wa-message, so the rebuild doesn't swap it back to the greeting.
if (typeof document !== 'undefined') {
  document.addEventListener(
    'click',
    (e) => {
      const a = e.target.closest?.(`a[href^="https://wa.me/${BOT_WHATSAPP_NUMBER}"]`);
      if (a) a.href = botWhatsAppHref(a.dataset.waMessage || undefined);
    },
    true,
  );
}
