# Source access and verification policy

Reviewed and live-tested 2026-10-09 from the Windows development machine. The
registry is `sources/registry.yaml`; runtime source controls are stored in SQLite.
Dates here are validation dates, not guarantees that later offers remain valid.
No benefit amount or geographic entitlement is hardcoded in the registry.

## Actual coverage

The first full live scan selected 15 enabled sources and produced 34 candidates:
14 checked successfully (including two unchanged), one rejected by the response
size cap. Google Cloud was subsequently changed to its smaller official program
documentation and checked successfully. Thus all 15 enabled sources have a
successful live validation, across those runs. A success means the configured
page/feed/API parsed; it does not mean every claim or event was verified.

| ID | Adapter / official location | Validation |
|---|---|---|
| cloudflare-workers | HTML, [Workers pricing](https://developers.cloudflare.com/workers/platform/pricing/) | 200, then conditional/unchanged |
| groq-billing | HTML, [billing FAQs](https://console.groq.com/docs/billing-faqs) | 200 |
| aws-activate | HTML, [startup credits](https://aws.amazon.com/startups/credits) | 200 |
| google-cloud | HTML, [Free Program documentation](https://docs.cloud.google.com/free/docs/free-cloud-features) | 200 after replacing oversized marketing page |
| microsoft-startups | HTML, [Startups](https://www.microsoft.com/en-us/startups) | 200 |
| github-students | HTML, [Student Pack](https://education.github.com/pack) | 200 |
| supabase-pricing | HTML, [pricing](https://supabase.com/pricing) | 200 |
| neon-pricing | HTML, [pricing](https://neon.com/pricing) | 200 |
| vercel-hobby | HTML, [Hobby documentation](https://vercel.com/docs/plans/hobby) | 200 |
| huggingface-blog | RSS, [official feed](https://huggingface.co/blog/feed.xml) | 200, then unchanged; five entries per cycle |
| cloudflare-blog | RSS, [official feed](https://blog.cloudflare.com/rss/) | 200; five entries |
| github-blog | RSS, [official feed](https://github.blog/feed/) | 200; five entries |
| ollama-releases | API, [repository releases](https://api.github.com/repos/ollama/ollama/releases?per_page=5) | 200; five releases |
| transformers-releases | API, [repository releases](https://api.github.com/repos/huggingface/transformers/releases?per_page=5) | 200; five releases |
| mlh-events | HTML, [current 2027 season](https://www.mlh.com/seasons/2027/events) | 200; structured individual event leads, organizer eligibility remains unknown |
| devpost | HTML, [hackathon listing](https://devpost.com/hackathons) | Disabled; access/event-rule review outstanding, not live-tested |
| hn-community | RSS, [public community feed](https://news.ycombinator.com/rss) | Explicit smoke blocked by robots.txt; remains disabled |
| hn-search | API, [public search](https://hn.algolia.com/api) | Explicit smoke HTTP 200, five unverified leads; optional, remains disabled |

## Source-specific limits

- GitHub public releases use unauthenticated requests. The primary limit is
  [60 requests/hour per originating IP](https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api), shared with other applications.
  Default six-hour cadence and five entries per source remain far below that by
  themselves. HTTP 429/Retry-After is respected; no credential bypass is attempted.
- Feeds expose announcements, not proof of a redeemable offer. Ordinary feed and
  release records stay in News. Search/community entries have no trusted domains
  and enter a review queue; they cannot self-authorize domain ownership.
- The [Algolia HN search repository](https://github.com/algolia/hn-search) was
  archived in February 2026. Its public search is optional, with no uptime or
  comprehensive web-search promise. Only its `/api/v1/search*` interface is accepted
  by this search adapter; there is no arbitrary JSON fetch proxy.
- X, Instagram, Reddit, authenticated browser sessions, paid search, CAPTCHA
  workarounds and login scraping are not enabled. They are not baseline dependencies.

## Common collection policy

Each source has a stable ID, adapter, provider/domain registry, category/family,
enabled flag, cadence, timeout, item budget, minimum interval, extraction selector,
optional terms URL and access notes. A configured URL is not a successful fetch.
Health includes attempt/success/change times, HTTP status, latency, parsed and
verified yield and errors. Disabled sources do not enter a full-scan roster.

Collection sends an identifying user agent, respects robots.txt, serializes a
host's requests, and defaults to at least two seconds between requests. Unknown
robots failures fail closed; 404/410 means no robots policy. Content is limited to
2 MB and known text/HTML/XML/JSON types. Compressed responses are rejected rather
than risking an unbounded decompression bomb. ETag/Last-Modified and hashes detect
unchanged responses. Retries are bounded and large Retry-After values defer work.
Per-run host circuits stop repeated failures. Native HTTP connections preserve TLS
verification and pin DNS-validated public addresses; redirects undergo the same checks.

## Evidence limits

Exact field excerpts, URL, retrieval time and content hash support claims.
Provider ownership alone does not verify an offer. The extractor keeps a candidate
partially verified unless benefit, geographic scope, payment requirement and
conditions meet explicit gates on the registered terms page. No real candidate
in the initial live scan satisfied the complete gate; this is expected, not a
reason to relax it. Broad program/pricing pages can span multiple plans, so the
evidence drawer and official terms must be consulted before taking action.

The generic extractor deliberately leaves many fields unknown. It does not infer
Chennai delivery/stock, student status, startup approval, exact date cutoffs or
lowest-ever discounts. The event strategy extracts individual schema.org Event
cards and explicit start/end timestamps without turning an event end into an
application deadline. External organizers require domain review. Separate configured
terms URLs are fetched through the same safe pipeline; explicit exclusions and
conflicts update field evidence. They do not automatically promote a broad listing
to Verified. Arbitrary linked-page crawling and comprehensive shopping-source
coverage are outside the measured source roster.
