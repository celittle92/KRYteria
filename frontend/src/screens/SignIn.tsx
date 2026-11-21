import { useCallback, useEffect, useState } from "react";
import { api, type Account, type DemoCharacter } from "../api";
import { ErrorNote, Spinner } from "../components/ui";

/**
 * The front door, and the onboarding moment.
 *
 * The privacy promise is HERE, before anybody types anything — not buried in terms. It
 * is the reason somebody would feel able to write the things this product asks for, so
 * it belongs on the screen where they decide whether to.
 */
export default function SignIn({ onSignedIn, theme, onToggleTheme }: {
  onSignedIn: (a: Account) => void;
  theme: "dark" | "warm";
  onToggleTheme: () => void;
}) {
  // Signing in is the default, not creating an account.
  //
  // This opened on "up", so arriving at the app put you in a create-account form with
  // no choice made. Somebody who meant to sign in gets a second, empty account instead,
  // and on the hosted demo that also means claiming a character's handle before the
  // seeder has taken it. In an app whose whole promise is that it holds as little as
  // possible, a stray click should not create an account.
  const [mode, setMode] = useState<"in" | "up" | "recover">("in");
  const [handle, setHandle] = useState("");
  const [passphrase, setPassphrase] = useState("");
  const [recoveryCode, setRecoveryCode] = useState("");

  // Shown once, after sign-up or a reset, before going any further. The plaintext exists
  // in that one response and nowhere else — not in the database, not re-sendable — so if
  // the user walks past this panel it is genuinely gone.
  const [issued, setIssued] = useState<{ code: string; account: Account } | null>(null);
  const [copied, setCopied] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [enteringAs, setEnteringAs] = useState<string | null>(null);

  // Three states, not two. This was `catch(() => setCharacters([]))`, which rendered a
  // failed fetch exactly like a deployment that has no demo data: nothing at all, with
  // no explanation and no way to retry.
  //
  // That is not a rare case here. A free instance sleeps after fifteen minutes and takes
  // about a minute to wake, so the very first request from a new browser — a fresh
  // window, an incognito window, a grader opening the link — is the one most likely to
  // lose a race with the boot. The result was a sign-in screen whose only route in had
  // silently removed itself, leaving a handle-and-passphrase form to somebody who has
  // neither.
  const [characters, setCharacters] = useState<DemoCharacter[] | null>(null);
  const [charactersFailed, setCharactersFailed] = useState(false);

  const loadCharacters = useCallback(async (attempt = 0) => {
    setCharactersFailed(false);
    try {
      setCharacters(await api.demoCharacters());
    } catch {
      // Wake-up takes about a minute, so retry a few times before giving up and saying
      // so. Backing off rather than hammering a container that is still starting.
      if (attempt < 4) {
        setTimeout(() => loadCharacters(attempt + 1), 4000 * (attempt + 1));
      } else {
        setCharacters([]);
        setCharactersFailed(true);
      }
    }
  }, []);

  useEffect(() => { loadCharacters(); }, [loadCharacters]);

  // What this deployment actually keeps. Asked rather than assumed, and left null on a
  // failure: an unanswered question must not render as a reassurance.
  const [storage, setStorage] = useState<{ durable: boolean; note: string } | null>(null);
  useEffect(() => {
    api.health()
      .then((h) => setStorage({
        durable: h.storage_durable !== false, note: String(h.storage_note ?? "") }))
      .catch(() => setStorage(null));
  }, []);

  async function enterDemo(c: DemoCharacter) {
    setEnteringAs(c.handle);
    setError(null);
    try {
      onSignedIn(await api.demoSignIn(c.handle));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not open the demo.");
      setEnteringAs(null);
    }
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      if (mode === "in") {
        onSignedIn(await api.signIn(handle.trim(), passphrase));
      } else if (mode === "up") {
        const a = await api.signUp(handle.trim(), passphrase);
        setIssued({ code: a.recovery_code, account: a });
      } else {
        const a = await api.recover(handle.trim(), recoveryCode.trim(), passphrase);
        setIssued({ code: a.recovery_code, account: a });
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="min-h-screen flex flex-col">
      <div className="flex justify-end p-5">
        <button onClick={onToggleTheme} className="text-muted hover:text-ink"
                aria-label="Switch theme">
          {theme === "dark" ? "☾" : "☀"}
        </button>
      </div>

      <div className="flex-1 mx-auto max-w-5xl w-full px-5 pb-16 grid lg:grid-cols-2 gap-14 items-center">
        <div className="rise">
          <h1 className="font-serif text-4xl sm:text-5xl leading-tight">KRYteria</h1>
          <p className="text-muted mt-2">Knowledge. Relationships. You.</p>

          <p className="voice text-2xl sm:text-3xl mt-10 leading-snug max-w-reading">
            Relationships are complicated.<br />Standards are not.
          </p>

          <p className="text-muted mt-6 max-w-reading leading-relaxed">
            Know what you want. Recognize what you have. Decide what you do next.
            KRYteria compares what you say matters to you against what you are actually
            experiencing — and leaves every decision to you.{" "}
            {/* The sentence four testers needed and nobody had written. Two of them
                feared being judged BY it; Deborah L. read it as matchmaking three times.
                It is the charter's founding line — the standards are never judged, only
                the reasoning — said on the first screen instead of kept in a document. */}
            <strong className="text-ink font-medium">
              It never scores you, ranks you, or tells you to stay or go.
            </strong>
          </p>

          {/* **One decision, above the fold.**
            *
            * Measured on the build before this one, at 375px: the homepage ran 2,947px —
            * about nine phone screens — and the only emphasized button on it was *Sign
            * in*, the one thing a visitor cannot do. The nine demo characters sat below
            * all of it under "Look around first", listed by age and occupation, saying
            * nothing about what was inside any of them.
            *
            * That matters more than it sounds: every tester so far used a phone, and the
            * app was designed on a laptop where the two columns sit side by side.
            *
            * Christine's call on the order: **starting an account is the goal**, and the
            * demo is the explainer rather than the destination. */}
          <div className="mt-9 max-w-reading space-y-3">
            {/* Not `btn-accent` / `btn-quiet`: those are `inline-flex` pills, which lays a
                label and its subtext out side by side. These need to stack. */}
            <button
              className="w-full text-left rounded-xl px-4 py-3.5 bg-accent text-accent-ink
                         hover:opacity-90 transition-colors"
              onClick={() => {
                setMode("up");
                document.getElementById("account-panel")
                  ?.scrollIntoView({ behavior: "smooth", block: "start" });
              }}
            >
              <span className="block font-medium">Start my own</span>
              <span className="block text-sm opacity-80 mt-0.5">
                No email needed. Choose a handle only you know.
              </span>
            </button>

            <button
              className="w-full text-left rounded-xl px-4 py-3.5 border border-line
                         text-ink hover:border-muted transition-colors
                         disabled:opacity-50 disabled:cursor-wait"
              disabled={enteringAs !== null}
              /* **Jane, not `demo`.** This pointed at the hand-built walkthrough for
               * about an hour, and Christine's verdict was exact: *"The primary
               * walkthrough is fucking terrible. Barely any analysis from the agents."*
               *
               * She was right and the number was already in front of me. `demo` is the
               * ONLY demo account in the database with **zero evidence links and zero
               * interrogations** — 9 observations that map to nothing. I chose it on
               * entry count and assessment count and never looked at the tables that
               * actually render as the agents having reasoned.
               *
               * `theintentionalist` has 25 observations, 24 evidence links across all
               * three relations, 9 interrogations, and the two patterns that are this
               * product's whole thesis: a Mandatory standard whose definition quietly
               * moved, and a decision postponed three times.
               *
               * `demo` keeps its place in the drawer — it is the only account that shows
               * one person judged under four profiles — but it is not the thing to lead
               * with. */
              onClick={() => enterDemo({ handle: "theintentionalist", name: "Jane" })}
            >
              {enteringAs === "theintentionalist"
                ? <Spinner label="Opening the demo…" />
                : (
                  <>
                    <span className="block font-medium">See it working</span>
                    <span className="block text-sm text-muted mt-0.5">
                      Learn how KRYteria works with a completed journal.
                    </span>
                  </>
                )}
            </button>

            <p className="text-sm text-faint">
              <button className="underline hover:text-muted"
                      onClick={() => {
                        setMode("in");
                        document.getElementById("account-panel")
                          ?.scrollIntoView({ behavior: "smooth", block: "start" });
                      }}>
                I already have an account
              </button>
            </p>
          </div>

          <div className="mt-10 space-y-4 max-w-reading">
            <h2 className="eyebrow">What this is, and is not</h2>
            <ul className="text-sm text-muted space-y-2.5">
              <li className="flex gap-3">
                <span className="text-accent shrink-0">—</span>
                <span>
                  <strong className="text-ink font-medium">No one else can see this.</strong>{" "}
                  There is no sharing, no collaborative assessment, and no way for anyone
                  to learn they have been mentioned. Being written about here is
                  indistinguishable, to them, from never having been written about.
                </span>
              </li>
              <li className="flex gap-3">
                <span className="text-accent shrink-0">—</span>
                <span>
                  <strong className="text-ink font-medium">You choose what is kept.</strong>{" "}
                  By default KRYteria keeps what it learned and erases what you wrote.
                  You can keep both, or neither.
                </span>
              </li>
              <li className="flex gap-3">
                <span className="text-accent shrink-0">—</span>
                <span>
                  <strong className="text-ink font-medium">It won't just agree with you.</strong>{" "}
                  KRYteria doesn't validate conclusions. It validates your right to
                  examine them.
                </span>
              </li>
              <li className="flex gap-3">
                <span className="text-accent shrink-0">—</span>
                <span>
                  <strong className="text-ink font-medium">It is not therapy.</strong>{" "}
                  Not a therapist, a medical or legal service, or a crisis line.
                </span>
              </li>
            </ul>
            <p className="text-xs text-faint pt-2 leading-relaxed">
              Your reflection is sent to an AI provider in order to be read. KRYteria
              erases what you ask it to erase from its own storage; the provider's policy
              governs what happens on their side.
            </p>
          </div>
        </div>

        {issued ? (
          <div className="rise">
            <div className="card p-7 sm:p-8 max-w-md lg:ml-auto">
              <h2 className="font-serif text-xl">Write this down now</h2>
              <p className="text-sm text-muted mt-1.5">
                This is the only way back into your account if you forget your
                passphrase. There is no email on file to send a reset to — that is what
                keeps the account anonymous.
              </p>

              <p className="font-mono text-lg tracking-tight mt-5 p-4 rounded-lg
                            bg-accent/10 border border-accent/30 select-all break-words">
                {issued.code}
              </p>

              <button
                className="btn-ghost w-full mt-3"
                onClick={() => {
                  navigator.clipboard?.writeText(issued.code).then(
                    () => setCopied(true), () => setCopied(false));
                }}
              >
                {copied ? "Copied" : "Copy"}
              </button>

              <p className="text-xs text-faint mt-4">
                KRYteria stores only a hash of this code. It is not saved anywhere in
                readable form, cannot be shown to you again, and nobody here can look it
                up — including us. If you lose both this and your passphrase, the account
                cannot be opened by anyone.
              </p>

              <div className="divider my-6" />

              <button className="btn-accent w-full"
                      onClick={() => onSignedIn(issued.account)}>
                I have written it down
              </button>
            </div>
          </div>
        ) : (
        <div className="rise">
          {/* Anchored so the hero's buttons can bring it into view: on a phone the two
              columns stack, and this panel is below the fold. */}
          <div id="account-panel" className="card p-7 sm:p-8 max-w-md lg:ml-auto scroll-mt-6">
            <h2 className="font-serif text-xl">
              {mode === "up" ? "Create a private account"
                : mode === "recover" ? "Use a recovery code" : "Sign in"}
            </h2>
            <p className="text-sm text-muted mt-1.5">
              {mode === "up"
                ? "No email, no name. Choose a handle only you know."
                : mode === "recover"
                ? "The six words you were given when you created the account."
                : "Welcome back."}
            </p>

            {/* Before the first field, not after the button. Somebody who is about to
                write about their relationship needs to know what this instance keeps
                BEFORE they type, and a notice underneath the thing it qualifies is a
                notice written for the author rather than the reader. */}
            {storage && !storage.durable && (
              <div className="mt-5 rounded-lg border border-contradict/50 bg-contradict/10 p-4">
                <p className="eyebrow text-contradict">Nothing here is kept</p>
                <p className="text-sm text-ink mt-1.5 leading-relaxed">{storage.note}</p>
                <p className="text-xs text-muted mt-2 leading-relaxed">
                  The download is under Settings once you are in, and it gives you the
                  whole record in one file.
                </p>
              </div>
            )}

            <form onSubmit={submit} className="mt-6 space-y-4">
              <div>
                <label htmlFor="handle" className="eyebrow block">Handle</label>
                <input
                  id="handle"
                  className="field mt-2"
                  value={handle}
                  onChange={(e) => setHandle(e.target.value)}
                  autoComplete="username"
                  required
                  autoFocus
                />
              </div>
              {mode === "recover" && (
                <div>
                  <label htmlFor="recovery" className="eyebrow block">Recovery code</label>
                  <input
                    id="recovery"
                    className="field mt-2 font-mono"
                    placeholder="six-words-joined-by-hyphens-like-this"
                    value={recoveryCode}
                    onChange={(e) => setRecoveryCode(e.target.value)}
                    autoComplete="off"
                    required
                  />
                </div>
              )}
              <div>
                <label htmlFor="passphrase" className="eyebrow block">
                  {mode === "recover" ? "New passphrase" : "Passphrase"}
                </label>
                <input
                  id="passphrase"
                  type="password"
                  className="field mt-2"
                  value={passphrase}
                  onChange={(e) => setPassphrase(e.target.value)}
                  autoComplete={mode === "in" ? "current-password" : "new-password"}
                  required
                />
                {mode !== "in" && (
                  <p className="text-xs text-faint mt-2">
                    At least 10 characters. A few ordinary words in a row is both stronger
                    and easier to remember than a short scramble.
                  </p>
                )}
              </div>

              {error && <ErrorNote onDismiss={() => setError(null)}>{error}</ErrorNote>}

              <button type="submit" className="btn-accent w-full" disabled={busy}>
                {busy ? <Spinner label="" />
                  : mode === "up" ? "Create account"
                  : mode === "recover" ? "Reset my passphrase" : "Sign in"}
              </button>
            </form>

            <div className="divider my-6" />

            <div className="flex flex-col items-start gap-2">
              <button
                className="text-sm text-muted hover:text-ink transition-colors"
                onClick={() => {
                  setMode(mode === "up" ? "in" : "up");
                  setError(null);
                }}
              >
                {mode === "up"
                  ? "I already have an account"
                  : "I need to create an account"}
              </button>
              <button
                className="text-sm text-muted hover:text-ink transition-colors"
                onClick={() => {
                  setMode(mode === "recover" ? "in" : "recover");
                  setError(null);
                }}
              >
                {mode === "recover"
                  ? "Back to signing in"
                  : "I have lost my passphrase"}
              </button>
            </div>
          </div>

          {characters === null && (
            <div className="card p-7 sm:p-8 max-w-md lg:ml-auto mt-5">
              <Spinner label="Loading the demo…" />
              <p className="text-xs text-faint mt-3">
                A free instance sleeps when nobody has used it, so the first load after a
                quiet spell takes about a minute. Nothing is wrong.
              </p>
            </div>
          )}

          {charactersFailed && (
            <div className="card p-7 sm:p-8 max-w-md lg:ml-auto mt-5">
              <h2 className="font-serif text-xl">The demo did not load</h2>
              <p className="text-sm text-muted mt-1.5">
                The server did not answer in time. On a free instance that usually means
                it was asleep and is still waking up.
              </p>
              <button className="btn-accent w-full mt-5" onClick={() => loadCharacters()}>
                Try again
              </button>
            </div>
          )}

          {/* The nine characters used to be listed here, by age and occupation, under
              "Look around first". They are now a drawer INSIDE the demo — "Other
              scenarios" — because a stranger cannot choose between nine people before
              they know what the product does, and being asked to was the thing four
              testers actually failed at. See `components/scenarios.tsx`. */}
          {characters !== null && characters.length > 0 && (
            <p className="text-xs text-faint mt-5 max-w-md lg:ml-auto leading-relaxed">
              The demo holds {characters.length + 1} invented people, each with their own
              standards and their own private record. Open one from inside it. Nothing
              there describes a real person, and no account can see any other.
            </p>
          )}

          <p className="text-xs text-faint mt-5 max-w-md lg:ml-auto">
            There is no email on file, so nothing here is tied to who you are and no
            reset link can land in an inbox somebody else can read. A recovery code,
            given once when you sign up, is what gets you back in instead.
          </p>
        </div>
        )}
      </div>
    </div>
  );
}
