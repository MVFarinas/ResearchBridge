"""Scholarly metadata from open APIs: OpenAlex, NIH iCite, Crossref, the PMC ID converter.

Every client fetches through :class:`rbcore.http.PoliteFetcher` (rate-limited,
neutral User-Agent, size-limited) and every response is cached in Postgres
with the time it was fetched, which the reader shows as an "as of" date.
Sources and terms: OpenAlex data is CC0; iCite is public domain; Crossref
metadata is open (Retraction Watch data in it is cited as requested); the ID
converter is an NCBI service. None of them is a licence gate (decisions.md §1.1).
"""
