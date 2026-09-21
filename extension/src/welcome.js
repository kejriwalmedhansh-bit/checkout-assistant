// The welcome screen's one job: turn a click into granted host access.
//
// chrome.permissions.request() only works inside a real user gesture, and the
// gesture is spent by the first `await`. So the call is the FIRST statement in
// the click handler — nothing is read from storage, nothing is checked, before
// it. Awaiting the result afterwards is fine; awaiting anything before it is
// what breaks it, silently, with "must be called during a user gesture".
const HOST_PERMS = { origins: ["http://*/*", "https://*/*"] };

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

// The usage question. Saved the moment it is ticked or unticked, not on the
// Start button: that button's click has to reach chrome.permissions.request()
// with nothing before it (see the note at the top). Both panels show the same
// answer, so it can be changed after access is granted too.
const CONSENT_KEY = "dealo_usage_consent";
const boxes = [...document.querySelectorAll(".consent-box")];
chrome.storage.local.get(CONSENT_KEY).then((s) => {
  boxes.forEach((b) => { b.checked = s[CONSENT_KEY] === true; });
});
boxes.forEach((box) => box.addEventListener("change", () => {
  boxes.forEach((b) => { b.checked = box.checked; });
  chrome.storage.local.set({ [CONSENT_KEY]: box.checked });
}));

// Someone who already said yes and reopened this tab shouldn't be asked again.
chrome.permissions.contains(HOST_PERMS).then((has) => {
  if (has) showDone();
});
