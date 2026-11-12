# Should KRYteria hold a directory of support numbers at all?

**Open question, 2026-11-12.** Christine: *"maybe a repository of support numbers isn't
right either. I just don't know what the right answer is."*

This records what an actual verification pass found, so the decision is made on evidence
rather than instinct. **The data gathered is below and nothing is lost by waiting.**

---

## What verifying six countries actually turned up

Roughly fifteen minutes of checking organisations' own pages, five countries plus the EU.
Every one of these is a real finding, not a hypothetical:

| What happened | Why it matters |
|---|---|
| **Canada has no national domestic-violence line.** The Government of Canada's own page routes to **~30 provincial and territorial lines** across 13 jurisdictions. | A "national hotline" field assumes a shape some countries do not have. Anyone building this from memory would have invented one. |
| **`rapecrisis.org.uk/get-help/` returned HTTP 525.** The organisation's own site was down at the moment of checking. | The source of truth is not always reachable — including at the moment somebody needs it. |
| **`gov.uk/call-999-if-you-are-not-able-to-speak` returned 404.** | Even government URLs rot. A stored link is a future dead end. |
| **`triplezero.gov.au` redirected, then timed out twice.** Australia's official emergency-number page could not be read at all. | Could not verify `000` from the authoritative source. |
| **13YARN's own page contradicts itself**: body text says `13 92 76`, the logo's alt text says `13 92 176`. | An organisation's own site can be internally wrong. "Check the source" does not fully protect you. |
| **WAVE is not a helpline.** It is an umbrella network of ~190 NGOs; its listed numbers are an office, open **Mon–Thu 9:00–17:00**. | A plausible-looking "European women's helpline" that a careless implementation would list as a crisis line. This is the error that would have hurt somebody. |
| **Refuge's page says both "24 hours a day, 365 days a year" and "Monday to Friday, 10am–6pm"** (the latter appears to scope the BSL service, but the page is ambiguous). | Even a correct number can carry wrong hours. |

**Seven problems, six countries, one sitting.** Not one of them would have been visible to
somebody writing the file from memory — and all seven are in exactly the direction that
hurts: confidently wrong.

**This is the strongest possible argument for the instinct.** A static directory is a
promise to keep something accurate forever, made by a project that cannot keep it.

---

## But "no numbers at all" has its own failure mode

The charter is clear that offering support matters, and that a person should not have to
go hunting at the worst moment. Removing resources entirely trades one failure for
another.

## The options

**A — Keep a comprehensive curated directory.** What the mechanism currently supports.
Accurate today, drifts tomorrow, unbounded maintenance, and the long tail of countries is
infinite. *Rejected: the project cannot honour the promise.*

**B — No numbers; link out to a maintained directory.** Zero staleness in our data, but
adds a step in a crisis and the external URL rots too (see the 404 above). Also makes
KRYteria's safety response feel like a redirect.

**C — Emergency number only.** Nearly impossible to get wrong — but she already knows
her emergency number, and most of what the safety layer handles is not a 999 moment.

**D — Live lookup at request time.** No. It puts a network dependency in the path of a
crisis, and the query itself would reveal what she is looking for.

**E — RECOMMENDED: stop pretending to be a phonebook, and date everything.**

Narrow what KRYteria claims. In a safety moment its job is to recognise what she
described, not minimise it, ask whether she is safe, and make getting help easy — **not**
to be the authority on what help exists.

Concretely:
1. **Keep a small set that is actually verified** — one or two per country, national
   lines only, no attempt at coverage. The eight below qualify today.
2. **Show the verification date to the user, in the interface.** *"Checked 12 Nov 2026."*
   A dated number is honest in a way a bare number is not, and it lets her judge.
3. **Say plainly that numbers change**, with the local emergency number as the fallback
   she already knows.
4. **Hand off for everything else** to one maintained directory, clearly labelled as
   somebody else's list.
5. **Never claim coverage we do not have.** An empty result stays an honest empty result.

This also fits the deadline. A global hotline directory is unbounded work on a project
with `report.html` and `slides.html` still unwritten.

---

## What was verified on 2026-11-12, if we proceed

Each from the organisation's own page. **Not yet committed to
`data/resources_international.json`** — that decision is open.

### United Kingdom
- **National Domestic Abuse Helpline** (Refuge) — `0808 2000 247` — "24 hours a day, 365
  days a year" — women and children — webchat at
  `nationaldahelpline.org.uk/chat-to-us-online/`
  Source: <https://www.nationaldahelpline.org.uk/> · **corroborated** on
  <https://www.gov.uk/report-domestic-abuse>
  *Caveat: the page also prints "Monday to Friday, 10am–6pm", which appears to scope BSL
  support. Ambiguous.*
- Emergency `999`, per <https://www.gov.uk/report-domestic-abuse>

### Ireland
- **Women's Aid** — `1800 341 900` — "24 hours a day, 7 days a week" — national freephone
  Source: <https://www.womensaid.ie/>
- **Dublin Rape Crisis Centre**, National 24-Hour Helpline — `1800 77 8888` — "open 24/7
  all year round" — sexual violence, national despite the name
  Source: <https://www.drcc.ie/>

### Australia
- **1800RESPECT** — `1800 737 732`, text `0458 737 732` — "free, 24 hours a day, 7 days a
  week" — domestic, family and sexual violence
  Source: <https://www.1800respect.org.au/>
- **13YARN** — Aboriginal and Torres Strait Islander crisis support — phone 24/7
  *Number NOT settled: the page prints `13 92 76` in body text and `13 92 176` in its
  logo. Do not publish until confirmed.*
- `000` appears on both pages, but the official Triple Zero source could not be read.

### New Zealand
- **Are You OK** family violence helpline — `0800 456 450` — "24/7", free
  Source: <https://www.areyouok.org.nz/>
  *The page does not use the name "It's Not OK"; confirm the official name.*
- **Safe to talk** (Sexual Harm Helpline) — `0800 044 334`, text `4334` — "24/7.
  Confidential. Free." — emergency `111` stated on the page
  Source: <https://safetotalk.nz/>

### Canada
- **No national domestic-violence line exists.** The Government of Canada page directs to
  provincial and territorial services.
  Source: <https://www.canada.ca/en/public-health/services/health-promotion/stop-family-violence/services.html>
- **ShelterSafe** — shelter-finder map, no phone line — <https://www.sheltersafe.ca/>
- **9-8-8 Suicide Crisis Helpline** — call or text `9-8-8` — "24/7/365" — *suicide crisis
  only, not domestic violence.* <https://988.ca/>
- Emergency `9-1-1`, with ShelterSafe noting **911 is not available in Nunavut**.

### Europe-wide
- **112** — "available everywhere in the EU, free of charge", also used in some non-EU
  countries and "available worldwide on GSM mobile networks"
  Source: <https://digital-strategy.ec.europa.eu/en/policies/112>
- **WAVE** — ~190-NGO umbrella network. **NOT a crisis line.** Maintains a list of
  national women's helplines across 46 European countries, which is the kind of handoff
  option E describes. <https://wave-network.org/find-help/>

---

## Not verified, and not to be written from memory

- Australia's `000` from the official source (page would not load).
- 13YARN's number (its own page disagrees with itself).
- Rape Crisis England & Wales, anything at all (site returned 525).
- The UK Silent Solution system (page 404).
- Whether the Refuge helpline serves anyone other than women, or covers all of the UK —
  its page states neither.
