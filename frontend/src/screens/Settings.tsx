import { useEffect, useState } from "react";
import { api, type Account, type Retention } from "../api";
import { Card, ErrorNote, Eyebrow, RETENTION_COPY, Section, Spinner } from "../components/ui";

/**
 * Settings, which here is mostly privacy.
 *
 * Retention, support-resource preference, export and deletion all live on one screen,
 * stated in plain language — not buried behind a "manage data" link.
 */
export default function Settings({ account, onChange }: {
  account: Account;
  onChange: (a: Account) => void;
}) {
  const [usage, setUsage] = useState<Record<string, unknown> | null>(null);
  const [retention, setRetention] = useState<Record<string, unknown> | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.usage().then(setUsage).catch(() => {});
    api.retentionReport().then(setRetention).catch(() => {});
  }, []);

  async function save(p: Parameters<typeof api.setPreferences>[0]) {
    setBusy(true);
    try { onChange(await api.setPreferences(p)); }
    catch (e) { setError(e instanceof Error ? e.message : String(e)); }
    finally { setBusy(false); }
  }

  return (
    <div>
      {error && <div className="mb-6"><ErrorNote onDismiss={() => setError(null)}>{error}</ErrorNote></div>}

      <Section
        title="What KRYteria keeps"
        subtitle="Your default after a Brain Dump is processed. You can still choose differently for any single entry."
      >
        <div className="space-y-3">
          {(["discard", "analysis_only", "keep_all"] as Retention[]).map((r) => (
            <button
              key={r}
              className="choice block"
              aria-checked={account.retention === r}
              role="radio"
              disabled={busy}
              onClick={() => save({ retention: r })}
            >
              <span className="block text-ink font-medium">{RETENTION_COPY[r].title}</span>
              <span className="block text-sm text-muted mt-1 leading-relaxed">
                {RETENTION_COPY[r].detail}
              </span>
            </button>
          ))}
        </div>

        {retention && (
          <Card className="p-5 mt-5">
            <Eyebrow>What is actually stored right now</Eyebrow>
            <ul className="text-sm text-muted space-y-1">
              <li>{String(retention.entries)} entries</li>
              <li>{String(retention.originals_still_stored)} still hold their original text</li>
              <li>{String(retention.originals_erased)} have had the original erased</li>
              <li>{String(retention.observations_kept)} observations kept</li>
            </ul>
            <p className="text-xs text-faint mt-3">{String(retention.note)}</p>
          </Card>
        )}
      </Section>

      <Section
        title="Support resources"
        subtitle="If KRYteria notices something concerning, how should it handle offering help?"
      >
        <div className="space-y-3">
          {([
            ["proactive", "Offer them when it seems relevant"],
            ["on_request", "Only when I ask"],
            ["suppressed", "Don't offer them"],
          ] as const).map(([value, label]) => (
            <button
              key={value}
              className="choice block"
              aria-checked={account.resource_offering === value}
              role="radio"
              disabled={busy}
              onClick={() => save({ resource_offering: value })}
            >
              <span className="text-ink">{label}</span>
            </button>
          ))}
        </div>
        <p className="text-xs text-faint mt-4 max-w-reading leading-relaxed">
          Whatever you choose, if you ever describe immediate danger KRYteria will still
          show emergency options. You can always find resources yourself from this page,
          and declining them never stops you asking.
        </p>

        <div className="mt-6">
          <label htmlFor="region" className="block text-ink text-sm">
            Where should KRYteria look for support services?
          </label>
          <p className="text-xs text-faint mt-1 mb-2 max-w-reading leading-relaxed">
            Optional. Emergency numbers differ between countries, so without this
            KRYteria will only show services that work anywhere — it would rather show
            you nothing than a number that does not work where you are. It never works
            this out from your connection, and you can clear it at any time.
          </p>
          <div className="flex items-center gap-2">
            <input
              id="region"
              className="field w-28"
              defaultValue={account.region ?? ""}
              placeholder="e.g. GB"
              maxLength={2}
              disabled={busy}
              aria-describedby="region-help"
              onBlur={(e) => {
                const v = e.target.value.trim().toUpperCase();
                if (v !== (account.region ?? "")) save({ region: v });
              }}
            />
            {account.region && (
              <button
                className="text-xs underline text-faint"
                disabled={busy}
                onClick={() => save({ region: "" })}
              >
                Clear
              </button>
            )}
          </div>
          <p id="region-help" className="text-xs text-faint mt-2">
            Two-letter country code. Nothing else about your location is stored.
          </p>
        </div>
      </Section>

      <Section title="Your data" subtitle="Yours to take, and yours to destroy.">
        <div className="flex flex-wrap gap-3">
          <button
            className="btn-quiet"
            onClick={async () => {
              const blob = new Blob([JSON.stringify(await api.export(), null, 2)],
                                    { type: "application/json" });
              const url = URL.createObjectURL(blob);
              const a = document.createElement("a");
              a.href = url;
              a.download = "kryteria-export.json";
              a.click();
              URL.revokeObjectURL(url);
            }}
          >
            Download everything
          </button>
          <button className="btn-quiet" onClick={() => api.signOut().then(() => location.reload())}>
            Sign out
          </button>
        </div>
        <DeleteAccount />
      </Section>

      <Section title="This install" subtitle="What KRYteria is running and what it costs.">
        {!usage ? <Spinner label="" /> : (
          <Card className="p-5">
            <ul className="text-sm text-muted space-y-1">
              <li>Mode: {String(usage.mode)}</li>
              <li>Model: {String(usage.model)}</li>
              <li>
                Cost:{" "}
                {usage.cost_available
                  ? `$${Number((usage.today as Record<string, unknown>)?.cost_usd ?? 0).toFixed(4)} today`
                  : "unavailable — no published prices are loaded"}
              </li>
            </ul>
            {usage.note ? <p className="text-xs text-faint mt-3">{String(usage.note)}</p> : null}
          </Card>
        )}
      </Section>

      <Section title="What this is not" subtitle="">
        <Card className="p-6">
          <p className="text-sm text-muted leading-relaxed max-w-reading">
            KRYteria is not therapy, a medical or legal service, or a crisis line. It does
            not diagnose anybody, and it will not tell you to stay or to leave. Your
            reflections are sent to an AI provider in order to be read — KRYteria erases
            what you ask it to erase from its own storage, and the provider's policy
            governs what happens on their side.
          </p>
          <p className="text-sm text-muted leading-relaxed max-w-reading mt-4">
            Nobody can see your account. There is no sharing, and no way for anyone to
            learn they have been mentioned here.
          </p>
        </Card>
      </Section>
    </div>
  );
}

function DeleteAccount() {
  const [open, setOpen] = useState(false);
  const [passphrase, setPassphrase] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!open) {
    return (
      <button className="text-sm text-contradict hover:underline mt-6 block"
              onClick={() => setOpen(true)}>
        Delete my account and everything in it
      </button>
    );
  }

  return (
    <Card className="p-6 mt-6 border-contradict/40">
      <h3 className="font-serif text-lg">Delete everything</h3>
      <p className="text-sm text-muted mt-2 max-w-reading leading-relaxed">
        Every entry, criterion, profile, assessment and decision is removed — not hidden,
        not archived. This cannot be undone, and because there's no email on file there is
        no way to recover it. Download your data first if you want it.
      </p>
      <label htmlFor="del" className="eyebrow block mt-5">Confirm with your passphrase</label>
      <input id="del" type="password" className="field mt-2 max-w-sm" value={passphrase}
             onChange={(e) => setPassphrase(e.target.value)} autoComplete="current-password" />
      {error && <div className="mt-4"><ErrorNote onDismiss={() => setError(null)}>{error}</ErrorNote></div>}
      <div className="flex gap-3 mt-5">
        <button
          className="btn border border-contradict text-contradict hover:bg-contradict hover:text-ground"
          disabled={busy || !passphrase}
          onClick={async () => {
            setBusy(true); setError(null);
            try { await api.deleteAccount(passphrase); location.reload(); }
            catch (e) { setError(e instanceof Error ? e.message : String(e)); }
            finally { setBusy(false); }
          }}
        >
          Delete everything permanently
        </button>
        <button className="btn-quiet" onClick={() => setOpen(false)}>Keep my account</button>
      </div>
    </Card>
  );
}
