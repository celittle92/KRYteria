import { useCallback, useEffect, useState } from "react";
import { NavLink, Navigate, Route, Routes, useLocation } from "react-router-dom";
import { api, type Account } from "./api";
import { Spinner } from "./components/ui";
import SignIn from "./screens/SignIn";
import BrainDump from "./screens/BrainDump";
import Criteria from "./screens/Criteria";
import Journal from "./screens/Journal";
import Checklist from "./screens/Checklist";
import Patterns from "./screens/Patterns";
import Reflection from "./screens/Reflection";
import ProgressScreen from "./screens/Progress";
import Settings from "./screens/Settings";

/**
 * Brain Dump is first in the navigation and first in the tab order, because it is the
 * primary interaction — not an optional chatbot buried in the interface.
 */
const NAV = [
  { to: "/", label: "Brain Dump", end: true },
  // Second, right after writing: rereading what you wrote and what KRYteria made of it
  // is the other half of the primary interaction, and it had no screen at all.
  { to: "/journal", label: "Journal" },
  { to: "/criteria", label: "My KRYteria" },
  { to: "/checklist", label: "Checklist" },
  { to: "/patterns", label: "Patterns" },
  { to: "/reflection", label: "Reflection" },
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

export default function App() {
  const [account, setAccount] = useState<Account | null>(null);
  const [checking, setChecking] = useState(true);
  const { theme, toggle } = useTheme(account);
  const location = useLocation();

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
                <span className="hidden sm:inline text-[11px] text-complicate">
                  Demonstration account — all content is invented
                </span>
              )}
              <button
                onClick={toggle}
                className="text-muted hover:text-ink text-sm transition-colors"
                aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} theme`}
                title={`Switch to ${theme === "dark" ? "light" : "dark"} theme`}
              >
                {theme === "dark" ? "☾" : "☀"}
              </button>
            </div>
          </div>

          <nav className="flex gap-1 overflow-x-auto -mb-px" aria-label="Main">
            {NAV.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.end}
                className={({ isActive }) =>
                  `px-3 py-2.5 text-sm whitespace-nowrap border-b-2 transition-colors ${
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
        <div key={location.pathname} className="rise">
          <Routes>
            <Route path="/" element={<BrainDump account={account} />} />
            <Route path="/journal" element={<Journal />} />
            <Route path="/criteria" element={<Criteria />} />
            <Route path="/checklist" element={<Checklist />} />
            <Route path="/patterns" element={<Patterns />} />
            <Route path="/reflection" element={<Reflection />} />
            <Route path="/progress" element={<ProgressScreen />} />
            <Route
              path="/settings"
              element={<Settings account={account} onChange={setAccount} />}
            />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </div>
      </main>

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
