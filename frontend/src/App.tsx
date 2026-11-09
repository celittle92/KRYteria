import { useCallback, useEffect, useState } from "react";
import { NavLink, Navigate, Route, Routes, useLocation } from "react-router-dom";
import { api, type Account } from "./api";
import { Spinner } from "./components/ui";
import SignIn from "./screens/SignIn";
import BrainDump from "./screens/BrainDump";
import Criteria from "./screens/Criteria";
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
  { to: "/criteria", label: "My KRYteria" },
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
    api.me().then(setAccount).catch(() => setAccount(null)).finally(() => setChecking(false));
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
            <Route path="/criteria" element={<Criteria />} />
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
