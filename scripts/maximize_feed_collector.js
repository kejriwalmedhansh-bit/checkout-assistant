// Maximize price + terms collection, run inside a logged-in maximize.money tab.
//
// Why a browser: the feed that carries per-payment-method rates
// (savemax.maximize.money/api/savemax/giftcard/details-v2, called
// details-max-coins until October 2026; same body, same fields) answers only
// a logged-in session, and Cloudflare blocks direct calls. Clicking every
// method on every page took ~3 hours; recording the page's own answers as each
// card opens takes ~10 minutes. Nothing here reads cookies or tokens — it
// records the responses the page already receives.
//
// How (2026-10-19): open https://www.maximize.money/gift-cards while logged
// in, paste this whole file into the console (or run it through Claude in
// Chrome's javascript tool), then:
//
//     __mxCatalog()               // the site's own full list (525 on 2026-10-19)
//     await __mxRun(IDS)          // IDS = [[path, giftCardId], ...] from
//                                 // db/maximize_catalog_raw.json (url, id)
//     await __mxRun(__mxNewIDS)   // cards in the list that IDS lacks
//     __mxProg                    // progress: {done, total, running}
//     __mxDownload()              // saves maximize_feed_<date>.json
//
// then: python3.11 scripts/import_maximize_feed.py ~/Downloads/maximize_feed_<date>.json --compare
//
// The list: since October 2026 the gift-cards page lists every card A-Z, but
// draws only what is on screen; the whole list sits in the grid component's
// props. It replaces the 3-hour search harvest — on 2026-10-19 it held 178
// cards the harvest never found (Cinepolis, District and others had moved to
// new ids; the old ids answer 404). It travels in the download as "__cards",
// and the importer adds new cards to db/maximize_catalog_raw.json.
//
// Keep the tab open. A hidden tab is fine: waits run on a worker timer, which
// Chrome does not slow down the way it slows a background tab's own timers.
// A card opened earlier in the same tab does not ask the feed again — start
// from a fresh tab for a full run.

window.__mx = window.__mx || {};
if (!window.__mxXhr) {
  const open = XMLHttpRequest.prototype.open, send = XMLHttpRequest.prototype.send;
  XMLHttpRequest.prototype.open = function (m, u) { this.__u = u; return open.apply(this, arguments); };
  XMLHttpRequest.prototype.send = function (body) {
    if (/giftcard\/details-(max-coins|v2)/.test(String(this.__u))) {
      this.addEventListener('load', () => { window.__mx[String(body)] = {status: this.status, text: this.responseText}; });
    }
    return send.apply(this, arguments);
  };
  window.__mxXhr = true;
}

if (!window.__sleep) {
  const w = new Worker(URL.createObjectURL(new Blob(
    ['onmessage=e=>setTimeout(()=>postMessage(e.data.id), e.data.ms)'], {type: 'text/javascript'})));
  let n = 0; const waiting = {};
  w.onmessage = e => { const f = waiting[e.data]; delete waiting[e.data]; f && f(); };
  window.__sleep = ms => new Promise(r => { const id = ++n; waiting[id] = r; w.postMessage({id, ms}); });
}

window.__mxGrab = async function (path, id, timeoutMs = 15000) {
  const key = JSON.stringify({giftCardId: id});
  delete window.__mx[key];
  window.next.router.push(path);
  const t0 = Date.now();
  while (Date.now() - t0 < timeoutMs) {
    if (window.__mx[key]) return window.__mx[key];
    await window.__sleep(250);
  }
  return null;
};

window.__mxRun = async function (ids) {
  window.__mxAll = window.__mxAll || {};
  window.__mxMiss = [];
  const todo = ids.filter(([, id]) => !window.__mxAll[id]);
  window.__mxProg = {done: 0, total: todo.length, running: true};
  for (const [path, id] of todo) {
    const r = await window.__mxGrab(path, id);
    if (r) window.__mxAll[id] = r; else window.__mxMiss.push([path, id]);
    window.__mxProg.done++;
    await window.__sleep(300);
  }
  window.__mxProg.running = false;
  return {collected: Object.keys(window.__mxAll).length, missed: window.__mxMiss.map(x => x[1])};
};

window.__mxCatalog = function () {
  const card = document.querySelector('[data-card-id]');
  if (!card) throw new Error('open maximize.money/gift-cards first');
  let f = card.parentElement[Object.keys(card.parentElement).find(k => k.startsWith('__reactFiber'))];
  while (f && !(f.memoizedProps && Array.isArray(f.memoizedProps.cards))) f = f.return;
  window.__mxCards = f.memoizedProps.cards.map(c => ({id: c.id, brand: c.brand, giftCardName: c.giftCardName,
                                                      stock: c.stock, channel: c.channel, discount: c.discount}));
  window.__mxNewIDS = (ids => window.__mxCards.filter(c => !ids.has(c.id)))(new Set((window.__mxIDS || []).map(x => x[1])))
    .map(c => ['/gift-cards/' + encodeURIComponent(c.brand.replace(/\s+/g, '')) + '/' + c.id, c.id]);
  return window.__mxCards.length;
};

window.__mxDownload = function () {
  if (window.__mxCards) window.__mxAll.__cards = {status: 0, text: JSON.stringify(window.__mxCards)};
  const a = document.createElement('a');
  a.href = URL.createObjectURL(new Blob([JSON.stringify(window.__mxAll)], {type: 'application/json'}));
  a.download = `maximize_feed_${new Date().toISOString().slice(0, 10)}.json`;
  document.body.appendChild(a); a.click(); a.remove();
};
