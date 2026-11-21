/**
 * "Other scenarios" — the nine demo people, reachable from inside the demo.
 *
 * **Christine's design, 2026-11-20:** *"I'm wondering if maybe the 9 populations should
 * be WITHIN the demo account, and almost like 'explore other scenarios'."* Right, and it
 * fixes the thing four testers failed at: they were asked to choose between nine
 * strangers **before** they knew what the product did. Nine doors, no signposts, and the
 * payoff three clicks inside one of them.
 *
 * **It is navigation, not data.** Each persona keeps her own account, her own criteria
 * library, her own profiles and people. Folding them into one account would collapse the
 * three-level model, and an account that contains other accounts is the single shape
 * this app's privacy rules forbid. Opening one here signs you into it and out of the one
 * you were in — which is what `POST /api/demo/signin` already does, and it already
 * refuses any account not flagged `is_demo`.
 *
 * **It renders only inside a demo account**, gated by the caller on
 * `account.is_demo === 1`. Not because it could leak anything — it cannot, the route
 * would 404 — but because this product's central promise is that no account can see any
 * other, and an affordance that *looks* like account-switching undercuts that even when
 * the data is safe.
 *
 * The line under each name is the character's own `demonstrates[0]`, authored with the
 * character and shipped in `data/characters/*.json`. **The API has been returning it
 * since the ecosystem was built and the front end threw it away**, listing age,
 * occupation and location instead — which is why the list told a visitor nothing about
 * what was inside any of them.
 */
import { useEffect, useState } from "react";
import { api, type Account, type DemoCharacter } from "../api";
import { Spinner } from "./ui";

export function ScenarioDrawer({ account, onSwitched, onClose }: {
  account: Account;
  onSwitched: (a: Account) => void;
  onClose: () => void;
}) {
  const [characters, setCharacters] = useState<DemoCharacter[] | null>(null);
  const [failed, setFailed] = useState(false);
  const [opening, setOpening] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    api.demoCharacters()
      .then((rows) => { if (!cancelled) setCharacters(rows); })
      .catch(() => { if (!cancelled) setFailed(true); });
    return () => { cancelled = true; };
  }, []);

  async function open(handle: string) {
    setOpening(handle);
    try {
      onSwitched(await api.demoSignIn(handle));
      onClose();
    } catch {
      setOpening(null);
      setFailed(true);
    }
  }

  return (
    <div className="fixed inset-0 z-40 flex items-end sm:items-center justify-center
                    bg-black/60 backdrop-blur-sm"
         role="dialog" aria-modal="true" aria-label="Other scenarios">
      <div className="bg-ground border-t sm:border border-line sm:rounded-2xl w-full
                      sm:max-w-lg max-h-[86vh] overflow-y-auto p-6 sm:p-7">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h2 className="font-serif text-xl">Other scenarios</h2>
            <p className="text-sm text-muted mt-1 leading-relaxed">
              Invented people, each with their own standards and their own private record.
              Opening one leaves this one — no account can ever see another.
            </p>
          </div>
          <button className="text-muted hover:text-ink text-xl leading-none shrink-0"
                  onClick={onClose} aria-label="Close">×</button>
        </div>

        {failed && (
          <p className="text-sm text-contradict mt-5">
            That did not load. The free instance may still be waking up.
          </p>
        )}
        {characters === null && !failed && (
          <div className="mt-6"><Spinner label="Loading the others…" /></div>
        )}

        <ul className="mt-5 space-y-2">
          {/* The demonstration account itself, which is a different thing from the nine:
              it is a hand-built exhibit of the rules — the same person passing under one
              profile and failing under another, Not Applicable as a real answer, a
              finding with evidence on both sides. The nine are a realistic population. */}
          <li>
            <button
              onClick={() => open("demo")}
              disabled={opening !== null || account.handle === "demo"}
              className={`w-full text-left rounded-lg px-3.5 py-3 border transition-colors
                          disabled:cursor-default
                          ${account.handle === "demo"
                            ? "border-accent/40 bg-accent/5"
                            : "border-hair hover:border-accent hover:bg-accent/5"}`}
            >
              <span className="flex items-baseline justify-between gap-3">
                <span className="font-medium">The walkthrough</span>
                {account.handle === "demo"
                  ? <span className="text-xs text-accent">you are here</span>
                  : <span className="text-xs text-faint">two people, five weeks</span>}
              </span>
              <span className="block text-sm text-muted mt-0.5">
                A finding with evidence on both sides, and the same person judged
                differently under two profiles.
              </span>
              {opening === "demo" && (
                <span className="block mt-2"><Spinner label="Opening…" /></span>
              )}
            </button>
          </li>

          {(characters ?? []).map((c) => {
            const here = account.handle === c.handle;
            return (
              <li key={c.handle}>
                <button
                  onClick={() => open(c.handle)}
                  disabled={opening !== null || here}
                  className={`w-full text-left rounded-lg px-3.5 py-3 border transition-colors
                              disabled:cursor-default
                              ${here ? "border-accent/40 bg-accent/5"
                                     : "border-hair hover:border-accent hover:bg-accent/5"}`}
                >
                  <span className="flex items-baseline justify-between gap-3">
                    <span className="font-medium">{c.name}</span>
                    {here
                      ? <span className="text-xs text-accent">you are here</span>
                      : <span className="text-xs text-faint">
                          {[c.age, c.occupation].filter(Boolean).join(" · ")}
                        </span>}
                  </span>
                  {c.demonstrates?.[0] && (
                    <span className="block text-sm text-muted mt-0.5">
                      {c.demonstrates[0]}
                    </span>
                  )}
                  {opening === c.handle && (
                    <span className="block mt-2"><Spinner label="Opening…" /></span>
                  )}
                </button>
              </li>
            );
          })}
        </ul>

        <p className="text-xs text-faint mt-5 leading-relaxed">
          Demonstration data. An account you make for yourself is separate from all of
          these, and from everyone else's.
        </p>
      </div>
    </div>
  );
}
