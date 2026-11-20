/**
 * Put a criterion's name back where its row id leaked into prose.
 *
 * Found by Christine testing her own account, 19 November 2026. A cross-criterion note
 * read: *"concrete engagement with an interest that matters to you (115), and one chosen
 * travel experience relevant to 114."* Those are database row ids. `CrossCriterionNote`
 * carries `criterion_ids` as a structured field precisely so the sentence does not have
 * to, but nothing told the Reasoning agent that `explanation` is prose for a person, so
 * it repeated them inline. Her words: the ids threw her off a lot.
 *
 * `reasoning.md` now says to name criteria rather than number them, which is the real
 * fix. This is the net underneath it: a prompt cannot guarantee a model never slips, and
 * the cost of a slip here is the app showing its plumbing to the one person it is
 * supposed to be talking to.
 */

/** Numbers that are plainly a quantity rather than a reference, however they parse.
 *
 * Criterion ids are small integers, so a corpus of ordinary sentences will contain
 * numbers that collide with them — "20 minutes late", "3 times this month". Substituting
 * there would be worse than the bug: it would put somebody's standard in the middle of a
 * duration. A bare number is only treated as a reference when the word after it is not a
 * unit, and bracketed forms are substituted unconditionally because "(115)" in running
 * prose is never a measurement.
 */
const UNITS = new RegExp(
  "^\\s*(?:%|per\\s|am\\b|pm\\b|" +
  "second|minute|hour|day|week|month|year|time|times|" +
  "mile|km|kilometre|kilometer|dollar|pound|euro|cent|" +
  "person|people|entry|entries|message|text|call|date|night|" +
  "nd\\b|rd\\b|st\\b|th\\b)",
  "i",
);

export function withCriterionNames(
  text: string | null | undefined,
  byId: Map<number, string>,
): string {
  if (!text || byId.size === 0) return text ?? "";

  // Bracketed or parenthesised: "(115)" and "[47]" are references, never quantities.
  let out = text.replace(/[([](\d{1,7})[)\]]/g, (whole, digits: string) => {
    const name = byId.get(Number(digits));
    return name ? `(${name})` : whole;
  });

  // Bare: "relevant to 114". Only when the id is real AND what follows is not a unit.
  out = out.replace(/\b(\d{1,7})\b/g, (whole, digits: string, offset: number) => {
    const name = byId.get(Number(digits));
    if (!name) return whole;
    if (UNITS.test(out.slice(offset + whole.length))) return whole;
    return name;
  });

  return out;
}

/** Build the lookup the function above needs, from whatever the criteria endpoint returns. */
export function criterionNameMap(
  rows: { id: number; value: string }[] | null | undefined,
): Map<number, string> {
  return new Map((rows ?? []).map((c) => [c.id, c.value]));
}
