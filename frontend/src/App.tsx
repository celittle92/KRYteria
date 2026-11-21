import { useCallback, useEffect, useRef, useState } from "react";
import { NavLink, Navigate, Route, Routes, useLocation } from "react-router-dom";
import { api, type Account } from "./api";
import { Spinner } from "./components/ui";
import { ScenarioDrawer } from "./components/scenarios";
import { MIN_CRITERIA } from "./onboarding";
import SignIn from "./screens/SignIn";
import BrainDump from "./screens/BrainDump";
import Criteria from "./screens/Criteria";
import Journal from "./screens/Journal";
import Checklist from "./screens/Checklist";
import Patterns from "./screens/Patterns";
import ProgressScreen from "./screens/Progress";
import Settings from "./screens/Settings";

/**
 * Brain Dump is first in the navigation and first in the tab order, because it is the
 * primary interaction — not an optional chatbot buried in the interface.
 */
/**
 * The navigation, in the order somebody actually moves through the product.
 *
 * **Checklist is deliberately absent, and its route still works.** Christine, 2026-11-20:
 * *"It's much easier than the brain dump to use BUT it doesn't feel as helpful and it's
 * not clear what KRYteria agents do with it once you select whether something is clear
 * or not. It feels redundant."* She is describing a real gap rather than a preference —
 * ticking an indicator records an observation and deliberately does **not** move an
 * assessment, which is the correct rule and leaves the screen with no visible
 * consequence. It is P1 in the spec, it is built and tested, and `/checklist` still
 * loads for anyone who has the link. It is simply not one of the things a first-time
 * visitor should have to work out.
 *
 * **"Journal History" rather than "Journal"**, also hers: the Brain Dump is where you
 * write, so the other screen needs a name that says it is the record rather than a
 * second place to start.
 */
const NAV = [
  { to: "/", label: "Brain Dump", end: true },
  // Second, right after writing: rereading what you wrote and what KRYteria made of it
  // is the other half of the primary interaction, and it had no screen at all.
  { to: "/journal", label: "Journal History" },
  { to: "/criteria", label: "My KRYteria" },
  { to: "/patterns", label: "Patterns" },
  { to: "/progress", label: "My Progress" },
  { to: "/settings", label: "Settings" },
];

function useTheme(account: Account | null) {
  const [theme, setTheme] = useState<"dark" | "warm">(
    () => (localStorage.getItem("kryteria-theme") as "dark" | "warm") || "dark",
  );

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    localStorage.setItem("kryteria-theme", theme);
  }, [theme]);

  // The account's saved preference wins on first load, so the choice follows the person
  // to another device rather than living only in this browser.
  useEffect(() => {
    if (account?.theme) setTheme(account.theme);
  }, [account?.theme]);

  const toggle = useCallback(() => {
    setTheme((t) => {
      const next = t === "dark" ? "warm" : "dark";
      api.setPreferences({ theme: next }).catch(() => {
        /* a failed preference save is not worth interrupting anybody over */
      });
      return next;
    });
  }, []);

  return { theme, toggle };
}

/** Where a signed-in account should start.
 *
 * Brain Dump is the primary interaction and the right home for anybody who has told
 * KRYteria what they care about. For somebody who has not, it is the wrong first screen
 * and quietly the worst one: an empty account writing its first entry has no criteria to
 * map evidence to, so the single thing that distinguishes this product from a chatbot
 * cannot happen, and the first impression is of a text box that thought about it a while
 * and found nothing.
 *
 * So the first screen follows the state of the account rather than a constant. With no
 * criteria, My KRYteria comes first — name what matters, then write about what happened.
 *
 * It fires **once per session** rather than whenever the library is empty. A permanent
 * rule would bounce somebody straight back out of Brain Dump every time they clicked it,
 * which is a trap, and deciding for them twice is a different thing from showing them
 * where to start.
 */
function useFirstScreen(account: Account | null) {
  const [redirectTo, setRedirectTo] = useState<string | null>(null);
  // Which account this has already been decided for, and whether this page session has
  // ever held one. Both are refs rather than state: changing them must not itself cause
  // a render, or the effect below re-enters on its own bookkeeping.
  const decidedFor = useRef<number | null>(null);
  const hadSession = useRef(false);

  useEffect(() => {
    if (!account) {
      // Signed out. Forget the decision so the NEXT account gets its own, and drop any
      // pending redirect, which belonged to somebody else.
      decidedFor.current = null;
      setRedirectTo(null);
      return;
    }
    if (decidedFor.current === account.id) return;

    // Christine, 19 November: open a demo, sign out, create an account — and it lands on
    // Settings. Two bugs compounding, and both are about identity rather than routing.
    //
    //   1. The decision was made once per PAGE LOAD, not once per ACCOUNT, so a second
    //      sign-in in the same tab never got a first screen at all.
    //   2. Signing out leaves the router wherever the last session was standing. Sign out
    //      from Settings and the new account inherits /settings — another person's
    //      location, applied to somebody who has not chosen anything yet.
    //
    // So a redirect is allowed from ANY path when the account has just changed inside
    // this tab, and only from "/" on a cold load — where a deep link or a bookmark is
    // this person's own expressed intent and must be honored.
    const signedInJustNow = hadSession.current;
    decidedFor.current = account.id;
    hadSession.current = true;
    const mayRedirect = signedInJustNow || window.location.pathname === "/";

    let live = true;

    // A demonstration account opens on something that DEMONSTRATES.
    //
    // Opening a character used to land on Brain Dump: an empty compose box in somebody
    // else's account — the least illustrative screen in the app, shown first, with the
    // populated ones left to be found. The 19 November tester met exactly that and then
    // called the demo "a bit overwhelming", having arrived at each dense screen cold and
    // without a reason to be there. My Progress is the opposite end: criteria beside
    // observed experience, which is the one view a stateless chat cannot produce.
    if (account.is_demo === 1) {
      if (mayRedirect) setRedirectTo("/progress");
      return;
    }

    api.criteria()
      .then((rows) => {
        if (!live) return;
        if (rows.length < MIN_CRITERIA && mayRedirect) setRedirectTo("/criteria");
      })
      .catch(() => {
        /* A failed lookup must not strand anybody on a redirect; leave them on Brain
           Dump, which is the behavior this app had before. */
      });
    return () => { live = false; };
  }, [account]);

  return { redirectTo, clear: useCallback(() => setRedirectTo(null), []) };
}

export default function App() {
  const [account, setAccount] = useState<Account | null>(null);
  const [checking, setChecking] = useState(true);
  const [scenariosOpen, setScenariosOpen] = useState(false);
  const { theme, toggle } = useTheme(account);
  const location = useLocation();
  const firstScreen = useFirstScreen(account);

  // Spend the redirect the moment it has been taken. Leaving it set would send somebody
  // back to My KRYteria every single time they clicked Brain Dump — a nudge that cannot
  // be declined is not a nudge, and "nudge, never block" is the rule this app already
  // states for profile defaults in `choice.ts`.
  const { redirectTo, clear } = firstScreen;
  useEffect(() => {
    if (redirectTo && location.pathname === redirectTo) clear();
  }, [redirectTo, location.pathname, clear]);

  useEffect(() => {
    // `?demo=<handle>` opens that demo character directly — so a link can point at the
    // exact view being written about, rather than at a sign-in screen plus instructions.
    // The report, the slides and anyone sharing a specific account all want this.
    //
    // It can only ever open a demo account: /api/demo/signin refuses anything not
    // flagged is_demo, so a handle in a URL is not a way into somebody's journal. An
    // existing session wins, so a link cannot sign a real user out of their own account
    // by accident.
    const wanted = new URLSearchParams(window.location.search).get("demo");

    api.me()
      .then(setAccount)
      .catch(async () => {
        if (!wanted) return setAccount(null);
        try {
          setAccount(await api.demoSignIn(wanted));
          // Take the parameter back out of the address bar: leaving it there would
          // re-open that account on every later reload, including after signing out.
          window.history.replaceState({}, "", window.location.pathname);
        } catch {
          setAccount(null);   // falls through to the sign-in screen, which says so
        }
      })
      .finally(() => setChecking(false));
  }, []);

  if (checking) {
    return (
      <div className="min-h-screen grid place-items-center">
        <Spinner label="Opening KRYteria" />
      </div>
    );
  }

  if (!account) {
    return <SignIn onSignedIn={setAccount} theme={theme} onToggleTheme={toggle} />;
  }

  return (
    <div className="min-h-screen flex flex-col">
      <header className="border-b border-line sticky top-0 bg-ground/95 backdrop-blur z-20">
        <div className="mx-auto max-w-5xl px-5">
          <div className="flex items-center justify-between h-14">
            <div className="flex items-baseline gap-3 min-w-0">
              <span className="font-serif text-lg tracking-tight">KRYteria</span>
              <span className="hidden sm:inline text-xs text-faint truncate">
                Knowledge. Relationships. You.
              </span>
            </div>
            <div className="flex items-center gap-3">
              {account.is_demo === 1 && (
                <>
                  <span className="hidden sm:inline text-[11px] text-complicate">
                    Demonstration account — all content is invented
                  </span>
                  {/* **Demo accounts only**, and the gate is the point rather than a
                    * precaution. The route would 404 on a real account anyway — but this
                    * product's central promise is that no account can see another, and an
                    * affordance that LOOKS like account-switching undercuts that even
                    * where the data is safe. */}
                  <button
                    onClick={() => setScenariosOpen(true)}
                    className="text-complicate hover:text-ink text-[11px] transition-colors
                               border border-complicate/40 rounded px-2 py-0.5"
                  >
                    Other scenarios
                  </button>
                </>
              )}
              <button
                onClick={toggle}
                className="text-muted hover:text-ink text-sm transition-colors"
                aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} theme`}
                title={`Switch to ${theme === "dark" ? "light" : "dark"} theme`}
              >
                {theme === "dark" ? "☾" : "☀"}
              </button>
              {/* **The way out, where you can see it.**
                *
                * Deborah L., 70, Massachusetts, 2026-11-20: she opened a demo and could
                * not find her way back to the first page. Signing out lived in Settings
                * — seven nav items along, under a heading about preferences — which is
                * findable if you already know the convention that accounts live behind a
                * settings gear, and invisible if you do not.
                *
                * Two testers, two versions of one problem: Alex could not find the way
                * *in* (no criteria step), Deborah could not find the way *out*. Neither
                * is a missing feature; both are a route that existed and was never shown.
                *
                * It says "Leave demo" rather than "Sign out" on a demo account because
                * that is the sentence she was looking for — nobody thinks of a sample
                * account as something they are signed in to. */}
              <button
                onClick={() => api.signOut().then(() => window.location.assign("/"))}
                className="text-muted hover:text-ink text-sm transition-colors
                           border border-line rounded px-2 py-0.5"
              >
                {account.is_demo === 1 ? "Leave demo" : "Sign out"}
              </button>
            </div>
          </div>

          {/* **Wraps on a phone instead of scrolling sideways.**
            *
            * Measured at 375px: the strip is 697px wide in a 335px viewport, so roughly
            * half the app's destinations sat off-screen behind a horizontal scroll with
            * no affordance saying so. Four testers could not find things; one of them
            * could not find the way out. A hidden navigation item is the same failure as
            * a rule enforced in a layer nobody reaches.
            *
            * Two rows of seven is not elegant. It is visible, which beats elegant. */}
          <nav className="flex flex-wrap gap-1 -mb-px sm:flex-nowrap sm:overflow-x-auto"
               aria-label="Main">
            {NAV.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.end}
                className={({ isActive }) =>
                  `px-2.5 py-2 text-[13px] sm:px-3 sm:py-2.5 sm:text-sm
                   whitespace-nowrap border-b-2 transition-colors ${
                    isActive
                      ? "border-accent text-ink"
                      : "border-transparent text-muted hover:text-ink"
                  }`
                }
              >
                {item.label}
              </NavLink>
            ))}
          </nav>
        </div>
      </header>

      <main className="flex-1 mx-auto max-w-5xl w-full px-5 py-10">
        {/* Rendered OUTSIDE the "/" route on purpose. Hanging it off that route meant it
            could only fire from the home path — which is useless for the case that found
            this: signing out of a demo from /settings and creating an account, where the
            new session inherits the old one's location and never passes through "/". */}
        {redirectTo && location.pathname !== redirectTo && (
          <Navigate to={redirectTo} replace />
        )}
        <div key={location.pathname} className="rise">
          <Routes>
            <Route path="/" element={<BrainDump account={account} />} />
            <Route path="/journal" element={<Journal />} />
            <Route path="/criteria" element={<Criteria />} />
            <Route path="/checklist" element={<Checklist />} />
            <Route path="/patterns" element={<Patterns />} />
            {/* Reflection is now a section of My Progress. The route stays so
                older links and bookmarks land somewhere sensible. */}
            <Route path="/reflection" element={<Navigate to="/progress" replace />} />
            <Route path="/progress" element={<ProgressScreen />} />
            <Route
              path="/settings"
              element={<Settings account={account} onChange={setAccount} />}
            />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </div>
      </main>

      {scenariosOpen && account.is_demo === 1 && (
        <ScenarioDrawer
          account={account}
          onSwitched={(a) => {
            setAccount(a);
            // A different person's record — start them where that account opens, not on
            // whichever screen the previous one happened to be showing.
            window.location.assign("/");
          }}
          onClose={() => setScenariosOpen(false)}
        />
      )}

      <footer className="border-t border-line">
        <div className="mx-auto max-w-5xl px-5 py-6 text-xs text-faint flex flex-wrap gap-x-6 gap-y-2">
          <span>Knowledge is the tool. Relationships are the context. You are the priority.</span>
          <span className="ml-auto">
            KRYteria is not therapy and not a crisis service.
          </span>
        </div>
      </footer>
    </div>
  );
}
