/**
 * Shopper login by SMS code (Firebase phone sign-in), used only when someone
 * buys a voucher inside Dealo. Loaded on demand so the rest of the site never
 * downloads Firebase.
 *
 * Firebase keeps the login in this browser until the shopper signs out, so a
 * returning buyer skips the number and code entirely. (Safari clears site
 * data after 7 days without a visit; those shoppers simply log in again.)
 */
const CONFIG = {
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY,
  authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN,
  projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID,
  appId: import.meta.env.VITE_FIREBASE_APP_ID,
};

let authPromise;

function auth() {
  if (!authPromise) {
    authPromise = Promise.all([import('firebase/app'), import('firebase/auth')]).then(([app, fa]) => {
      const a = fa.getAuth(app.initializeApp(CONFIG));
      a.languageCode = 'en';
      // Local testing only: Firebase's test numbers skip the robot check.
      // Never set in a real build — it would let bots trigger SMS freely.
      if (import.meta.env.VITE_FIREBASE_TEST_MODE === 'true') a.settings.appVerificationDisabledForTesting = true;
      return { a, fa };
    });
  }
  return authPromise;
}

/** The signed-in shopper, or null. Waits for Firebase to restore a saved login. */
export async function currentUser() {
  const { a } = await auth();
  await a.authStateReady();
  return a.currentUser;
}

let verifier;

/**
 * Sends the SMS. `buttonId` is the "Get code" button: Firebase's robot check
 * runs invisibly on it and only shows a puzzle when it suspects a bot.
 */
export async function sendCode(phone10, buttonId) {
  const { a, fa } = await auth();
  if (!verifier) verifier = new fa.RecaptchaVerifier(a, buttonId, { size: 'invisible' });
  return fa.signInWithPhoneNumber(a, `+91${phone10}`, verifier);
}

/** Exchanges the typed code for a login. Returns Firebase's ID token. */
export async function confirmCode(confirmation, code) {
  const { user } = await confirmation.confirm(code);
  return user.getIdToken();
}

export async function idToken() {
  const user = await currentUser();
  return user ? user.getIdToken() : null;
}
