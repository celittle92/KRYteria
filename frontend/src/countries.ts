/**
 * ISO 3166-1 alpha-2 codes, for the "where should KRYteria look for support services?"
 * setting.
 *
 * WHY THIS IS A DROPDOWN. It was a free-text box, and Christine's reaction was the
 * answer: *"How would people know what this is? It's kinda not intuitive."* Nobody
 * should have to know that Britain is GB and Germany is DE to find a helpline.
 *
 * AND THE EXAMPLE LIST SHE SKETCHED PROVED THE POINT. It had "SK - South Korea". **SK
 * is Slovakia. South Korea is KR.** That is not a knock on her — it is the whole
 * argument. Country codes are exactly the kind of thing people are confidently wrong
 * about, and being confidently wrong here means someone in Seoul gets shown nothing
 * while the app believes it is helping. A list you pick from cannot make that mistake.
 *
 * Two other near-misses worth knowing, for whoever edits this next: **UK is not an ISO
 * country code** (it is reserved, and GB is the real one), and **EU is not one either**
 * — 112 is handled as a GLOBAL row rather than a country.
 *
 * Names are the common English short forms people will actually scan for, not the full
 * ISO legal names ("United Kingdom", not "United Kingdom of Great Britain and Northern
 * Ireland"). The list is ordered alphabetically by name so it can be scanned.
 */

export interface Country { code: string; name: string }

export const COUNTRIES: Country[] = [
  { code: "AR", name: "Argentina" },
  { code: "AU", name: "Australia" },
  { code: "AT", name: "Austria" },
  { code: "BD", name: "Bangladesh" },
  { code: "BE", name: "Belgium" },
  { code: "BR", name: "Brazil" },
  { code: "CA", name: "Canada" },
  { code: "CL", name: "Chile" },
  { code: "CN", name: "China" },
  { code: "CO", name: "Colombia" },
  { code: "HR", name: "Croatia" },
  { code: "CZ", name: "Czechia" },
  { code: "DK", name: "Denmark" },
  { code: "EG", name: "Egypt" },
  { code: "EE", name: "Estonia" },
  { code: "FI", name: "Finland" },
  { code: "FR", name: "France" },
  { code: "DE", name: "Germany" },
  { code: "GH", name: "Ghana" },
  { code: "GR", name: "Greece" },
  { code: "HK", name: "Hong Kong" },
  { code: "HU", name: "Hungary" },
  { code: "IS", name: "Iceland" },
  { code: "IN", name: "India" },
  { code: "ID", name: "Indonesia" },
  { code: "IE", name: "Ireland" },
  { code: "IL", name: "Israel" },
  { code: "IT", name: "Italy" },
  { code: "JM", name: "Jamaica" },
  { code: "JP", name: "Japan" },
  { code: "KE", name: "Kenya" },
  { code: "LV", name: "Latvia" },
  { code: "LT", name: "Lithuania" },
  { code: "LU", name: "Luxembourg" },
  { code: "MY", name: "Malaysia" },
  { code: "MT", name: "Malta" },
  { code: "MX", name: "Mexico" },
  { code: "MA", name: "Morocco" },
  { code: "NL", name: "Netherlands" },
  { code: "NZ", name: "New Zealand" },
  { code: "NG", name: "Nigeria" },
  { code: "NO", name: "Norway" },
  { code: "PK", name: "Pakistan" },
  { code: "PE", name: "Peru" },
  { code: "PH", name: "Philippines" },
  { code: "PL", name: "Poland" },
  { code: "PT", name: "Portugal" },
  { code: "RO", name: "Romania" },
  { code: "SA", name: "Saudi Arabia" },
  { code: "SG", name: "Singapore" },
  { code: "SK", name: "Slovakia" },
  { code: "SI", name: "Slovenia" },
  { code: "ZA", name: "South Africa" },
  { code: "KR", name: "South Korea" },
  { code: "ES", name: "Spain" },
  { code: "LK", name: "Sri Lanka" },
  { code: "SE", name: "Sweden" },
  { code: "CH", name: "Switzerland" },
  { code: "TW", name: "Taiwan" },
  { code: "TH", name: "Thailand" },
  { code: "TR", name: "Türkiye" },
  { code: "UA", name: "Ukraine" },
  { code: "AE", name: "United Arab Emirates" },
  { code: "GB", name: "United Kingdom" },
  { code: "US", name: "United States" },
  { code: "VN", name: "Vietnam" },
];

/** Countries KRYteria actually has a checked resource for, as of 2026-11-12. */
export const COUNTRIES_WITH_RESOURCES = new Set(["AU", "CA", "IE", "NZ", "GB", "US"]);

export function countryName(code: string | null): string | null {
  if (!code) return null;
  return COUNTRIES.find((c) => c.code === code)?.name ?? code;
}
