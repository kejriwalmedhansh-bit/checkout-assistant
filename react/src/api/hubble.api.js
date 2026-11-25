/** Buying a voucher inside Dealo through Hubble (see src/api/routers/hubble.py). */
import { apiClient } from './client';

export const hubbleApi = {
  /** GET /hubble/offer -> { available, offer } */
  offer: async (merchant, price, inStore = false, bestPct = null, link = null) => {
    const params = { merchant, price: Math.round(price), in_store: inStore };
    if (bestPct != null) params.best_pct = bestPct;
    // The result's store link: its website finds the shop when Google's shop
    // name doesn't ("Decathlon Sports India" -> decathlon.in -> Decathlon).
    if (link) params.link = link;
    const { data } = await apiClient.get('/hubble/offer', { params });
    return data;
  },
  /** GET /hubble/brand -> { available, brand:{discount_pct, cards, min_amount, max_amount, typed, in_store} } — shop-name search, no cart yet. */
  brand: async (merchant, bestPct = null, { slug = null, inStore = false } = {}) => {
    // A buy link names the voucher by slug (/buy/ajio-luxe); a shop-name
    // search names the shop. One of the two. inStore: the link's ?store=1
    // (Lifestyle sells an online and an in-store card under one name).
    const params = slug ? { slug } : { merchant };
    if (bestPct != null) params.best_pct = bestPct;
    if (inStore) params.in_store = true;
    const { data } = await apiClient.get('/hubble/brand', { params });
    return data;
  },
  /** POST /hubble/session -> { url, offer } — the link that opens Hubble on the pay step. */
  session: async (body) => {
    const { data } = await apiClient.post('/hubble/session', body);
    return data;
  },
  /** POST /hubble/login -> { name, email, new } — right after the SMS code; new numbers are then asked their name. */
  login: async (idToken, source = {}) => {
    // source: where this visit came from (visitSource), kept on the buyer's record the first time,
    // plus the visit's own tag (dealo_id or visit_id) so the login joins the visit in Mixpanel.
    const { data } = await apiClient.post('/hubble/login', { id_token: idToken, ...source });
    return data;
  },
  /** POST /hubble/heard-from -> { ok } — the one-tap answer to "How did you hear about Dealo?". */
  heardFrom: async (idToken, choice) => {
    const { data } = await apiClient.post('/hubble/heard-from', { id_token: idToken, choice });
    return data;
  },
  /** POST /hubble/account -> { ok } — logging in from "Your account" without buying. */
  account: async (body) => {
    const { data } = await apiClient.post('/hubble/account', body);
    return data;
  },
  /** GET /hubble/me -> { phone, total_saved, total_bought, purchases:[{brand, amount, saved, at}] } — "Your account". */
  me: async (idToken) => {
    const { data } = await apiClient.get('/hubble/me', { headers: { Authorization: `Bearer ${idToken}` } });
    return data;
  },
  /** GET /hubble/card[?ref] -> { url } — Hubble's own page for one gift card (code + PIN), or all of them. */
  card: async (idToken, ref = null) => {
    const { data } = await apiClient.get('/hubble/card', { params: ref ? { ref } : {}, headers: { Authorization: `Bearer ${idToken}` } });
    return data;
  },
  /** GET /hubble/orders/latest -> { found, brand, vouchers:[{code,pin,amount}] }
   * session (from /session) + brand: only the order this purchase made, so a
   * second voucher bought soon after never shows the first one's code. */
  latestOrder: async (idToken, { session = null, brand = null } = {}) => {
    const params = {};
    if (session) params.session = session;
    if (brand) params.brand = brand;
    const { data } = await apiClient.get('/hubble/orders/latest', { params, headers: { Authorization: `Bearer ${idToken}` } });
    return data;
  },
};
