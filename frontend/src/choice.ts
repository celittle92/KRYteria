/**
 * When KRYteria may choose for you, and when it must not.
 *
 * Christine's rule, 2026-11-12:
 *
 *   "Unless there is only one KRYteria profile the user built, then that one profile
 *    should be default. But if there are more than one profiles created (i.e. Boyfriend,
 *    Marriage, Casual), not one should be default, as that kind of goes against the
 *    brand philosophies of no relationship type is better than another, and no
 *    judgement."
 *
 * This is the "no profile ranks above another" rule reaching the interface. A default
 * is a soft recommendation — whichever profile is pre-selected is the one the product
 * implies is the normal case, and the product has no business implying that a marriage
 * is more normal than a one-night stand. With exactly one option there is no ranking to
 * make, so choosing it is help rather than a verdict.
 *
 * The same applies to the person. And a prompt is not the same as a default: when there
 * is a real choice to make, the control has to *say so* rather than sitting on a value
 * that looks chosen.
 */

/** The only option, if there is exactly one. Otherwise nothing is chosen for you. */
export function soleOrNone<T extends { id: number }>(items: T[]): number | "" {
  return items.length === 1 ? items[0].id : "";
}

/**
 * The first line of a dropdown.
 *
 * With several options this is a question, so an unselected control reads as "you have
 * not answered yet" rather than as a quietly made choice. With none, it is the plain
 * opt-out. With exactly one the list is already resolved, so the opt-out is all that is
 * needed.
 */
export function placeholderFor(count: number, prompt: string, optOut: string): string {
  return count > 1 ? prompt : optOut;
}

/**
 * Whether the user still owes an answer — several options exist and none is picked.
 * Used to nudge, never to block: an entry with nothing selected is still a valid entry,
 * because somebody mid-thought should not have to classify before they can write.
 */
export function awaitingChoice(count: number, value: number | ""): boolean {
  return count > 1 && value === "";
}
