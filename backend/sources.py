"""What counts as a source KRYteria will cite.

Christine's rule, 2026-11-09: *"I want to make sure the app ONLY uses reputable sources.
From like .gov or .edu or published papers. Nothing like... Goop and her unconscious
coupling nonsense."*

This is a gate, not a guideline. ``verify_research_note`` refuses a URL that does not
pass, so a well-meaning verification cannot quietly admit a wellness blog. Combined with
the rule that a citation must resolve to a verified row, the chain is closed end to end:

    agent cites a ref  →  ref resolves to a verified row  →  row was verified against a
    source on this list

WHY AN ALLOWLIST RATHER THAN A BLOCKLIST. A blocklist is a list of the bad sites somebody
has already thought of, and the one that matters is always the one nobody listed. An
allowlist is wrong in the safe direction: a legitimate publisher we forgot gets refused
and somebody adds it deliberately, which is a conversation rather than a silent mistake.

NOT ON THE LIST, ON PURPOSE:
  - Wikipedia. Useful for orientation, not a citation.
  - Psychology Today, Verywell, Healthline, and the rest of the popular-psychology tier.
  - Personal sites and blogs, however well regarded the author.
  - Scribd, Academia.edu, ResearchGate — uploads, not publications.
  - Booksellers, coaching sites, wellness brands, newsletters.
"""

from __future__ import annotations

import re
from urllib.parse import urlparse

#: Academic and government top-level domains. A university or a public health body is
#: acceptable on the strength of its domain alone.
TRUSTED_SUFFIXES = (
    ".gov", ".edu", ".gov.uk", ".gc.ca", ".europa.eu", ".who.int", ".nih.gov",
)

#: Most of the world's universities sit under a country-coded academic second level —
#: ``.ac.uk``, ``.ac.nz``, ``.edu.au``, ``.ac.ke``, ``.edu.ph`` and so on. Enumerating
#: them one country at a time means the list grows every time somebody needs a source
#: from a country nobody happened to think of, which is how an allowlist decays into
#: being worked around. The pattern is the rule.
#:
#: It is deliberately strict about shape: a two-letter country code only, so a
#: ``.edu.com``-style lookalike does not match.
ACADEMIC_CC = re.compile(r"\.(ac|edu)\.[a-z]{2}$")

#: Specific hosts that are neither .gov nor .edu but are the publisher of record, a
#: permanent identifier, or a library catalog. Each one is here because a human put it
#: here.
TRUSTED_HOSTS = {
    # Permanent identifiers and indexes
    "doi.org", "dx.doi.org", "pubmed.ncbi.nlm.nih.gov", "pmc.ncbi.nlm.nih.gov",
    "jstor.org", "www.jstor.org", "psycnet.apa.org",
    # Scholarly publishers
    "apa.org", "www.apa.org", "sciencedirect.com", "www.sciencedirect.com",
    "link.springer.com", "springer.com", "onlinelibrary.wiley.com", "wiley.com",
    "tandfonline.com", "www.tandfonline.com", "journals.sagepub.com", "sagepub.com",
    "academic.oup.com", "global.oup.com", "cambridge.org", "www.cambridge.org",
    "nature.com", "www.nature.com", "science.org", "www.science.org",
    "bmj.com", "www.bmj.com", "thelancet.com", "www.thelancet.com",
    "journals.plos.org", "annualreviews.org", "www.annualreviews.org",
    "guilford.com", "www.guilford.com", "press.princeton.edu", "yalebooks.yale.edu",
    "hup.harvard.edu", "mitpress.mit.edu", "us.macmillan.com",
    # Library catalogs — the right source for a book's bibliographic record
    "search.worldcat.org", "worldcat.org", "catalog.loc.gov", "lccn.loc.gov",
    "openlibrary.org",
}

#: Named so a refusal can say WHY, rather than only that the URL failed.
KNOWN_UNACCEPTABLE = {
    "wikipedia.org": "an encyclopaedia, useful for orientation but not a citation",
    "en.wikipedia.org": "an encyclopaedia, useful for orientation but not a citation",
    "psychologytoday.com": "popular psychology writing, not a primary source",
    "www.psychologytoday.com": "popular psychology writing, not a primary source",
    "verywellmind.com": "a consumer health site, not a primary source",
    "healthline.com": "a consumer health site, not a primary source",
    "goop.com": "a lifestyle brand",
    "scribd.com": "a document upload, with no guarantee of provenance",
    "www.scribd.com": "a document upload, with no guarantee of provenance",
    "researchgate.net": "an upload by an author, not the publication of record",
    "www.researchgate.net": "an upload by an author, not the publication of record",
    "academia.edu": "an upload site — note the .edu is the company's, not a university's",
    "www.academia.edu": "an upload site — note the .edu is the company's, not a university's",
    "medium.com": "a blogging platform",
    "gwern.net": "a personal site, however carefully maintained",
    "goodreads.com": "a bookseller's catalog, which this project has already seen be wrong",
    "www.goodreads.com": "a bookseller's catalog, which this project has already seen be wrong",
    "amazon.com": "a retailer",
    "www.amazon.com": "a retailer",
}


class UnacceptableSource(ValueError):
    """The URL is not somewhere KRYteria is willing to cite from."""


def check_source(url: str) -> str:
    """Return the host if the URL is acceptable, or raise explaining why not.

    ``academia.edu`` is why this cannot be a simple suffix test: the company owns a
    ``.edu``, and a naive ``.edu`` check would wave through an upload site.
    """
    if not (url or "").strip():
        raise UnacceptableSource("Verification needs the URL of what you actually opened.")

    parsed = urlparse(url.strip())
    if parsed.scheme not in ("http", "https"):
        raise UnacceptableSource(f"{url!r} is not a web address.")

    host = (parsed.hostname or "").lower()
    if not host:
        raise UnacceptableSource(f"{url!r} has no host.")

    # Named refusals first, so .edu lookalikes and well-known popular sites are rejected
    # with a reason rather than slipping through a suffix rule.
    for bad, why in KNOWN_UNACCEPTABLE.items():
        if host == bad or host.endswith("." + bad):
            raise UnacceptableSource(
                f"{host} is {why}. KRYteria cites primary sources: a journal, a "
                "publisher, a university, a government body, or a library catalog."
            )

    if host in TRUSTED_HOSTS:
        return host
    if any(host == s.lstrip(".") or host.endswith(s) for s in TRUSTED_SUFFIXES):
        return host
    if ACADEMIC_CC.search(host):
        return host

    raise UnacceptableSource(
        f"{host} is not a recognized scholarly source. KRYteria accepts .gov and .edu "
        "domains, scholarly publishers, permanent identifiers such as doi.org, and "
        "library catalogs. If this is a legitimate publisher the list has missed, add "
        "it to backend/sources.py deliberately rather than working around this."
    )


def is_acceptable(url: str) -> bool:
    try:
        check_source(url)
        return True
    except UnacceptableSource:
        return False
