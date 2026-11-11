/**
 * Vouchers bought through Dealo, kept on the buyer's own phone/browser.
 *
 * Dealo's server forgets codes 30 minutes after a purchase and never stores
 * them (src/api/routers/hubble.py). Before this, the code lived only on the
 * "Voucher ready" screen: a buyer who tapped through to Swiggy and came back
 * to a reloaded page had lost it (Sarthak, 11 Nov 2026). Now each code is
 * also kept here, in this browser only, and "Your vouchers" reopens it.
 */
import { useSyncExternalStore } from 'react';

const KEY = 'dealo_my_vouchers';
const PENDING_KEY = 'dealo_voucher_pending';
const KEEP_DAYS = 180;
const MAX = 30;
// How long after paying we still ask the server for the code on a fresh
// page load — the server keeps it for 30 minutes.
const PENDING_MS = 30 * 60 * 1000;

const listeners = new Set();
const notify = () => listeners.forEach((fn) => fn());

const read = (key) => {
  try {
    return JSON.parse(localStorage.getItem(key) || 'null');
  } catch {
    return null;
  }
};
const write = (key, value) => {
  try {
    if (value == null) localStorage.removeItem(key);
    else localStorage.setItem(key, JSON.stringify(value));
  } catch {
    /* private mode / storage full: the on-screen copy still works */
  }
};

let cache = null;
const fresh = (list) => {
  const cutoff = Date.now() - KEEP_DAYS * 86400000;
  return (Array.isArray(list) ? list : []).filter((v) => v?.code && v.saved_at > cutoff);
};

export function savedVouchers() {
  if (cache === null) cache = fresh(read(KEY));
  return cache;
}

/** Keep every card of a finished order. Same code twice is stored once. */
export function saveOrder(order, extra = {}) {
  const cards = (order?.vouchers || []).filter((v) => v?.code);
  if (!cards.length) return;
  const now = Date.now();
  const added = cards.map((v) => ({
    code: String(v.code),
    pin: v.pin ? String(v.pin) : null,
    amount: v.amount ?? null,
    valid_till: v.valid_till ?? null,
    brand: order.brand || extra.brand || 'Voucher',
    add_voucher_url: extra.add_voucher_url || null,
    shop_link: extra.shop_link || null,
    in_store: Boolean(extra.in_store),
    saved_at: now,
  }));
  const codes = new Set(added.map((v) => v.code));
  cache = [...added, ...savedVouchers().filter((v) => !codes.has(v.code))].slice(0, MAX);
  write(KEY, cache);
  write(PENDING_KEY, null);
  notify();
}

export function forgetVoucher(code) {
  cache = savedVouchers().filter((v) => v.code !== code);
  write(KEY, cache);
  notify();
}

/** Paid, code not seen yet: lets a reloaded page fetch it from the server. */
export function markPending(extra) {
  write(PENDING_KEY, { ...extra, at: Date.now() });
}
export function pendingPurchase() {
  const p = read(PENDING_KEY);
  if (!p || Date.now() - p.at > PENDING_MS) return null;
  return p;
}
export function clearPending() {
  write(PENDING_KEY, null);
}

export function useSavedVouchers() {
  return useSyncExternalStore(
    (fn) => {
      listeners.add(fn);
      const onStorage = (e) => {
        if (e.key === KEY) {
          cache = null;
          fn();
        }
      };
      window.addEventListener('storage', onStorage);
      return () => {
        listeners.delete(fn);
        window.removeEventListener('storage', onStorage);
      };
    },
    savedVouchers,
    () => [],
  );
}

// Whether a buyer has logged in on this browser, so the top bar can show
// "Your account" without loading Firebase on every page (lib/firebase.js
// loads only when needed). Set after a buy-flow login, cleared on log out.
const SIGNED_KEY = 'dealo_signed_in';
let signedIn = null;
export function setSignedIn(value) {
  signedIn = Boolean(value);
  write(SIGNED_KEY, signedIn ? 1 : null);
  notify();
}
const readSignedIn = () => {
  if (signedIn === null) {
    // Buyers from before this flag existed still have their saved name.
    let hadName = false;
    try {
      hadName = Boolean(localStorage.getItem('dealo_buyer_name'));
    } catch {
      /* private mode */
    }
    signedIn = Boolean(read(SIGNED_KEY)) || hadName;
  }
  return signedIn;
};
/** True when this browser has a buyer: a login or any saved code. */
export function useHasAccount() {
  const vouchers = useSavedVouchers();
  const signed = useSyncExternalStore(
    (fn) => {
      listeners.add(fn);
      return () => listeners.delete(fn);
    },
    readSignedIn,
    () => false,
  );
  return signed || vouchers.length > 0;
}

// Opening the "Your vouchers" sheet from anywhere (top bar, menu, buy flow).
let open = false;
const openListeners = new Set();
export function setVouchersOpen(value) {
  open = value;
  openListeners.forEach((fn) => fn());
}
export function useVouchersOpen() {
  return useSyncExternalStore(
    (fn) => {
      openListeners.add(fn);
      return () => openListeners.delete(fn);
    },
    () => open,
    () => false,
  );
}
