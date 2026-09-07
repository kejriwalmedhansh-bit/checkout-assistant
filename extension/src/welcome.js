// The welcome screen's one job: turn a click into granted host access.
//
// chrome.permissions.request() only works inside a real user gesture, and the
// gesture is spent by the first `await`. So the call is the FIRST statement in
// the click handler — nothing is read from storage, nothing is checked, before
// it. Awaiting the result afterwards is fine; awaiting anything before it is
// what breaks it, silently, with "must be called during a user gesture".
const HOST_PERMS = { origins: ["http://*/*", "https://*/*"] };
const API_BASE = "https://dealo-backend.onrender.com";

const ask = document.getElementById("ask");
const done = document.getElementById("done");
const grant = document.getElementById("grant");
const foot = document.getElementById("foot");

function showDone() {
  ask.hidden = true;
  done.hidden = false;
}

grant.addEventListener("click", () => {
  // First statement. See the note above.
  chrome.permissions
    .request(HOST_PERMS)
    .then((granted) => {
      if (granted) {
        showDone();
        return;
      }
      // Declined. Say what that means and leave the button working — someone
      // who clicks Deny by reflex should be able to change their mind without
      // reinstalling the extension.
      foot.textContent =
        "Dealo can't check shops without that. Press the button again whenever you'd like to turn it on.";
      foot.classList.add("warn");
    })
    .catch(() => {
      foot.textContent =
        "Chrome wouldn't show the permission box. Try reopening this tab from the Dealo icon.";
      foot.classList.add("warn");
    });
});

document.getElementById("close").addEventListener("click", () => {
  window.close();
});

// The two figures on this screen are read from the live catalogue, never
// written into the page. A rate typed into HTML is true on the day it is typed
// and quietly false a fortnight later, and this is the first thing a stranger
// ever reads about Dealo — the worst possible place for a stale number.
//
// No host permission is needed for this: the backend answers with
// Access-Control-Allow-Origin: *, which is why this works on a screen shown
// BEFORE the shopper has granted anything.
//
// If it fails — offline, server asleep, anything — the page keeps the wording
// it shipped with. A welcome screen must never show a broken figure or a gap.
(async () => {
  try {
    const res = await fetch(`${API_BASE}/headline`, { signal: AbortSignal.timeout(4000) });
    if (!res.ok) return;
    const { typical_pct: typical, strong_pct: strong } = await res.json();
    if (strong) document.getElementById("hl-strong").textContent = `Up to ${strong}%`;
    if (typical) document.getElementById("hl-typical").textContent = `around ${typical}%`;
  } catch (e) {
    // Keep the shipped wording.
  }
})();

// Someone who already said yes and reopened this tab shouldn't be asked again.
chrome.permissions.contains(HOST_PERMS).then((has) => {
  if (has) showDone();
});
