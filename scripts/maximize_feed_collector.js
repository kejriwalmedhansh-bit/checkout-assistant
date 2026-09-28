// Maximize price + terms collection, run inside a logged-in maximize.money tab.
//
// Why a browser: the feed that carries per-payment-method rates
// (savemax.maximize.money/api/savemax/giftcard/details-max-coins) answers only
// a logged-in session, and Cloudflare blocks direct calls. Clicking every
// method on every page took ~3 hours; recording the page's own answers as each
// card opens takes ~10 minutes. Nothing here reads cookies or tokens — it
// records the responses the page already receives.
//
// How (2026-09-28): open any maximize.money gift-card page while logged in,
// paste this whole file into the console (or run it through Claude in Chrome's
// javascript tool), then call:
//
//     await __mxRun(IDS)          // IDS = [[path, giftCardId], ...] from
//                                 // db/maximize_catalog_raw.json (url, id)
//     __mxProg                    // progress: {done, total, running}
//     __mxDownload()              // saves maximize_feed_<date>.json
//
// then: python3.11 scripts/import_maximize_feed.py ~/Downloads/maximize_feed_<date>.json --compare
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
    if (String(this.__u).includes('details-max-coins')) {
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

window.__mxDownload = function () {
  const a = document.createElement('a');
  a.href = URL.createObjectURL(new Blob([JSON.stringify(window.__mxAll)], {type: 'application/json'}));
  a.download = `maximize_feed_${new Date().toISOString().slice(0, 10)}.json`;
  document.body.appendChild(a); a.click(); a.remove();
};
