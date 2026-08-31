# Source access and fallback

Record the strongest representation actually inspected, not the source that
would have been ideal.

## Access ladder

1. Open the canonical primary source or official document.
2. Try an alternate official representation: API, data export, HTML version,
   supplement, document index, or stable identifier lookup.
3. Use a lawful full-text repository or author/institutional manuscript, while
   recording that it is an alternate copy.
4. Use a registry or bibliographic record for metadata only.
5. Use a reputable secondary account when necessary and label it secondary.
6. If the remaining evidence cannot support the claim, leave it unresolved.

Do not bypass access controls, repeatedly hammer a blocked host, or imply that
an abstract, search snippet, DOI record, or registry stub is full text.

## Common failure modes

- **Publisher 403/paywall:** record `blocked`; try DOI, PubMed, PubMed Central,
  an official supplement, or an author/institutional manuscript. Metadata can
  establish bibliographic facts but normally cannot verify detailed outcomes.
- **ClinicalTrials.gov:** prefer the official API v2 or structured download when
  detailed fields are needed. Record the endpoint and query. A registration or
  posted result is not automatically evidence of a peer-reviewed publication.
- **Government URL drift:** search the agency's current official domain by
  document title, identifier, and date; inspect its index or data catalog; then
  record the new canonical URL. Archives establish historical availability but
  should be labeled as archived copies.
- **Dynamic or script-only page:** look for an official API, accessible HTML,
  PDF, export, or print representation. If none can be inspected, record the
  source as blocked or metadata-only.

Stop escalating once the expected value of another fallback is low or it would
require unsafe access. Report the resulting coverage limitation plainly.
