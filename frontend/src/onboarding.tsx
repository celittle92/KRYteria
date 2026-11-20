import { type ReactNode } from "react";
import { Link } from "react-router-dom";
import { Card, Eyebrow } from "./components/ui";

/**
 * The first thing a new account is told, and the one rule about when it is told.
 *
 * Found by a user test on 19 November 2026 (`output/user_test.md`). A tester clicked
 * every screen, wrote two entries, and never saw what the product does — because with no
 * criteria the Evidence agent cannot run, so his entries came back as extracted
 * observations and nothing else, and nothing told him why. He ended up proposing, as a
 * feature request, the thing KRYteria already is: *"then over time the journal entries
 * can be analyzed"*. You cannot ask for what you have been shown.
 *
 * The cause was never discoverability — he found every screen. It was that the app had
 * no first step and said so nowhere. So this module exists to say one thing in one voice
 * from one place, rather than letting two screens drift into two different explanations.
 */

/** How many criteria before an entry can be analysed against anything.
 *
 * Three rather than one: a single criterion produces an analysis almost as thin as none,
 * and `MIN_SUPPORT` in the store already uses three as the floor below which this product
 * declines to claim a pattern. One number, one idea — below this, KRYteria says what it
 * cannot do yet instead of performing an analysis it cannot support.
 */
export const MIN_CRITERIA = 3;

/** Christine's copy, 19 November 2026. Used verbatim — this is brand voice, not UI text.
 *
 * Her instruction, and the reason it reads the way it does: *"Our first interaction
 * should be an invitation to define what matters, not a tutorial about how the app
 * itself works."* It is the charter's own line — the standards are never judged, only
 * the reasoning — said to somebody on their first screen rather than kept in a document.
 */
export function GettingStarted({ action }: { action?: ReactNode }) {
  return (
    <Card className="p-6 sm:p-8">
      <Eyebrow>Getting started</Eyebrow>
      <h2 className="font-serif text-2xl sm:text-3xl mt-1">Start with what matters to you.</h2>

      <div className="mt-4 space-y-3 text-muted leading-relaxed">
        <p>
          Before you can evaluate your experiences, you need to decide what is important.
        </p>
        <p>
          KRYteria starts with <strong className="text-ink">your</strong> criteria: the
          qualities, behaviours, values and preferences that matter to you in a
          relationship.
        </p>
        <p>
          They can be big or small, practical or personal. Maybe you value emotional
          maturity, a compatible sense of humour, shared interests, a great smile, or
          someone who remembers how you take your coffee.
        </p>
        <p>
          There are no right or wrong answers. No standards are too high, too low, too
          specific, or too unconventional. These are{" "}
          <strong className="text-ink">your</strong> KRYteria, and you decide what matters.
        </p>
        <p className="text-ink">
          <strong>
            Start by adding at least {MIN_CRITERIA} KRYteria. You can always change, add,
            or refine them as you go.
          </strong>
        </p>
      </div>

      <p className="mt-5 pt-4 border-t border-line text-sm text-faint">
        Your standards are yours. Your decisions are yours. KRYteria helps you see the
        evidence.
      </p>

      {action && <div className="mt-6">{action}</div>}
    </Card>
  );
}

/** The Brain Dump gate: an invitation with a way past it.
 *
 * Deliberately NOT a lock, and the reason is in the safety charter rather than in
 * anybody's taste. `orchestrator` runs Narrative and the Safety Layer together on the
 * raw text of an entry, with no criteria involved — so **writing is the only route to
 * the safety layer**. Locking this box until somebody has set up three standards would
 * put setup in front of a person who opened the app at 2am because something happened,
 * which is the charter's one documented exception turned inside out:
 *
 *   "A user must never have to mark physical safety, consent, or freedom from coercion
 *    as a Mandatory criterion before KRYteria recognises a serious concern."
 *
 * It is also what `choice.ts` already says about defaults — **nudge, never block** — and
 * what this screen's own copy promises: no forms, no required categories, no need to
 * organise your thoughts first.
 *
 * So the prominent path is criteria, and the way through is quiet rather than absent.
 * Most people take the button. The person who takes the small link is usually the person
 * who needs to.
 */
export function WriteAnyway({ onProceed }: { onProceed: () => void }) {
  return (
    <button
      onClick={onProceed}
      className="text-sm text-faint hover:text-muted underline underline-offset-2 transition-colors"
    >
      I just need to write something down
    </button>
  );
}

export function AddYourKryteria() {
  return (
    <Link to="/criteria" className="btn-accent inline-block">
      Add your KRYteria
    </Link>
  );
}
