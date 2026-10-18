# Measured performance

## Dynamic campaign, 2026-10-09

Real local SearXNG/GitHub campaign `d2b45a259fa448c096c690b795ebc977`, no fixtures:
**40.187 seconds**, two successful query responses, six nonseed repository metadata
observations, five successful nonseed web-page fetches, 61 queued URLs, 1,806,904
page-body bytes. Database observed at 9,240,576 bytes, system memory at 85.8% near
the end. These are activity counts, not 61 unique actionable or verified offers.
Search origins included developer-tool directories; no issuer claim was promoted
merely because the fetch succeeded. A separate real Chennai workshop query returned
27 results while one engine rate-limited. No internet-wide recall or comparative
chatbot superiority has been measured.

Subsequent real category-balanced campaign: **41.844 seconds**, three query responses,
two page attempts each for Food, Shopping and Travel, three successful pages and
three explicit failures (two HTTP 403, one DNS error), 80 new queued URLs. A small
Travel-only frontier follow-up took **26.593 seconds**: two successful pages
(Red Taxi and Agoda) and one MakeMyTrip timeout, 13 URLs queued. High memory caused
one-task dispatch; these checks did not bypass access restrictions. Successful page
access still does not prove an actionable benefit, availability or eligibility.

Deterministic delayed fixtures prove provisional-before-fetch visibility,
pause/resume/cancel, archive immutability, replay and browser subrequest blocking.
Their delays/yields are not live performance measurements. Later tests and coverage
updates are recorded in PROGRESS; README is the command reference.

Measured 2026-10-09. Python 3.11.9, Windows build 26200, Intel64 Family 6 Model 151
Stepping 2; default SQLite WAL and local OneDrive workspace disk. These measurements
are observations, not promised latencies or global-discovery guarantees.

## Live collection

| Run | Work | Wall time | Outcome |
|---|---|---:|---|
| Initial vertical slice | 4 real sources: HTML, feed and GitHub releases | 4.480 s | 4 success, 12 candidates |
| Initial full roster | 15 enabled sources | 22.482 s | 12 success + 2 unchanged + 1 size rejection, 34 unique candidates |
| Google replacement check | Smaller official documentation page | about 4.2 s | 200, one candidate |
| Final full roster after fixes | 15 enabled sources, warmed conditional cache | 16.975 s | All 15 success/unchanged, 35 candidates |
| Structured current-season events | One source with five Event cards | 4.565 s | 200, five individual event leads |
| Extraction refinement smoke | Cloudflare, Groq and Supabase | 3.592 s | All three sources completed, three candidates |

The full roster performed 33 fetches including robots/redirect work. Fetch p50 was
0.698 s and p95 6.399 s; four cache hits. Summed collection time was 77.714 s across
concurrent tasks; it overlaps and must not be added to wall time. Persistence time
was 0.343 s. Initial metrics combined parsing/verification with collection; later
instrumentation records extraction, verification and optional summary durations
separately. JSON metrics remain attached to each run in Scan activity.

The final full run recorded extraction 1.534 s, verification 0.293 s, persistence
0.586 s and 16 cache hits. Fetch p50 was 0.454 s, p95 2.097 s. Timings include
concurrent overlap and should not be summed. No real candidate met the complete
Verified gate; official claim excerpts produced conservative partial verification.

## Local filtering

`scripts/benchmark.py` creates an isolated temporary database with 10,000 fixture
versions and indexed FTS5 entries. It executes 30 search/category/sorted queries,
including exact total count and a 24-item first page. It never pollutes real results.

| Code state | Median | p95 |
|---|---:|---:|
| Initial schema | 95.68 ms | 111.92 ms |
| Added JSON expression indexes (migration 002) | 72.58 ms | 79.18 ms |

The dataset is intentionally simple and synthetic; this does not measure arbitrary
query terms, network latency, browser rendering, high-concurrency load, or million-row
performance. Wall-clock evidence is in the ignored `data/benchmark.json`; this report
preserves the measured summary. See [README](../README.md) for reproduction.

The production frontend with Tracker/Digest is approximately 260 kB JS (79.6 kB gzip)
and 17.1 kB CSS (4.4 kB gzip), excluding browser/runtime dependencies. No model is needed for these
results. Use actual full-cycle duration and source quotas to choose a cadence;
minute-level global discovery is not promised.
