import { useState } from "react";
import { api, type Account } from "../api";
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
  const [mode, setMode] = useState<"in" | "up">("up");
  const [handle, setHandle] = useState("");
  const [passphrase, setPassphrase] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const account = mode === "up"
        ? await api.signUp(handle.trim(), passphrase)
        : await api.signIn(handle.trim(), passphrase);
      onSignedIn(account);
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
            Know what you want. Recognise what you have. Decide what you do next.
            KRYteria compares what you say matters to you against what you are actually
            experiencing — and leaves every decision to you.
          </p>

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

        <div className="rise">
          <div className="card p-7 sm:p-8 max-w-md lg:ml-auto">
            <h2 className="font-serif text-xl">
              {mode === "up" ? "Create a private account" : "Sign in"}
            </h2>
            <p className="text-sm text-muted mt-1.5">
              {mode === "up"
                ? "No email, no name. Choose a handle only you know."
                : "Welcome back."}
            </p>

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
              <div>
                <label htmlFor="passphrase" className="eyebrow block">Passphrase</label>
                <input
                  id="passphrase"
                  type="password"
                  className="field mt-2"
                  value={passphrase}
                  onChange={(e) => setPassphrase(e.target.value)}
                  autoComplete={mode === "up" ? "new-password" : "current-password"}
                  required
                />
                {mode === "up" && (
                  <p className="text-xs text-faint mt-2">
                    At least 10 characters. A few ordinary words in a row is both stronger
                    and easier to remember than a short scramble.
                  </p>
                )}
              </div>

              {error && <ErrorNote onDismiss={() => setError(null)}>{error}</ErrorNote>}

              <button type="submit" className="btn-accent w-full" disabled={busy}>
                {busy ? <Spinner label="" /> : mode === "up" ? "Create account" : "Sign in"}
              </button>
            </form>

            <div className="divider my-6" />

            <button
              className="text-sm text-muted hover:text-ink transition-colors"
              onClick={() => { setMode(mode === "up" ? "in" : "up"); setError(null); }}
            >
              {mode === "up"
                ? "I already have an account"
                : "I need to create an account"}
            </button>
          </div>

          <p className="text-xs text-faint mt-5 max-w-md lg:ml-auto">
            Because there is no email on file, a lost passphrase cannot be reset — which
            is the same property that makes the account anonymous.
          </p>
        </div>
      </div>
    </div>
  );
}
