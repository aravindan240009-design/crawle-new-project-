# Validation

Canonical setup, test, live-scan and benchmark commands are in [README](../README.md).
Offline tests use isolated temporary SQLite databases. No fixture enters the live
database. Browser tests launch a separate local backend on port 8766 with a
timestamped demo data directory; fixture cards and banner explicitly say DEMO.

## Deterministic coverage

- `tests/test_discovery.py`: unknown nonseed domain → immediate provisional → fetched
  evidence → searchable/exportable live item → scheduled revisit; cancellation,
  pause/resume, generation fencing, single-page interrupted retry, category fairness,
  immutable archives, cross-process campaign locking, real Crawlee dispatch with
  fixture transport, issuer identity/ambiguous branches/reposts, radius unknowns,
  ISO travel-window precision, repository licenses/releases/timed trends, media
  captions committed into live history/digest, rules/quiet hours/corrections/deadlines.
- `tests/test_discovery_browser.py`: actual Chromium executes fixture JavaScript
  while private subrequests are blocked; captions preserve timestamps and missing
  OCR reports a precise reason. Browser test skips only if optional Chromium is absent.

- `tests/test_evidence.py`: identity/tracking canonicalization, distinct regions,
  lookalike domains, India/exclusion/ambiguous-global rules, supported evidence,
  card trials/conflicts, date-only precision, feed/release parsing, invalid feeds,
  model-disabled operation and rejection of unsupported summary content.
- `tests/test_scans.py`: real child-process overlap exclusion and expired lease
  recovery, atomic staging/history, cancel while collecting, independent user state,
  partial/all failure, missing rediscovery, alert idempotency, filter/export parity,
  exact deadline unknowns, CSV injection and Asia/Kolkata schedule calculations.
- `tests/test_security_api.py`: loopback/private/link-local/mapped-IPv6 rejection,
  validated connection target pinning (DNS rebinding), unsafe redirects, robots,
  oversized content, conditional 304 cache, 429 Retry-After, localhost Host/Origin/
  session-token checks, parameter validation and persisted state through the API.
- `tests/test_operations.py`: schedule catch-up/coalescing across worker restarts,
  online backup, restore into a new directory, a fresh Python process reading saved
  notes, restore disarming, model-unavailable fallback, and no-due-source skipped run.
- `tests/test_planning.py`: digest staging/exclusion gates, changes while alerts
  are disabled, tracking persistence across versions/restarts, exact date validation,
  IST reminder catch-up/dedup, closed-status suppression, protected mutations and
  calendar/Markdown export. Personal reminders never become official deadlines.
- `frontend/src/*.test.*`: safe external links, escaped content, non-color-only
  verification badges, labeled filter interaction, unknown time and IST formatting.
- `frontend/e2e/radar.spec.ts`: native server → first fixture scan → live progress →
  published cards → search → field evidence → bookmark/notes → reload persistence;
  desktop and mobile overflow/screenshots; settings persistence/disarmed scheduling;
  source toggle persistence; tracker status/reminder save and reload, tracker view,
  digest view, calendar output. Full process persistence is independently tested above.
  A third scenario exercises dynamic discovery events, provisional-before-fetch,
  pause/resume, SSE cursor replay, local alert-rule creation and mobile overflow.

## Results and environment

86 backend tests passed on Windows/Python 3.11.9 in 30.25 seconds. Five frontend
tests and the TypeScript/Vite production build passed. Three Chromium browser
scenarios passed in 26.2 seconds. Real desktop/mobile inspection recorded no
JavaScript page errors or horizontal overflow. Dynamic live measurements are in
BENCHMARKS; platform/runtime gaps are in SOURCE_CAPABILITIES.

One intermediate targeted test run overlapped a frontend rebuild and saw the
temporarily absent asset directory. After the build, the affected test passed;
the final full suite also passed. Run builds before tests requiring static assets.
The browser tests exposed a missing save confirmation inside the modal and a
reload race in tests that did not await persistence; both were corrected. Requests
now have explicit timeout/abort behavior instead of an indefinite loading state.

One non-failing upstream Starlette warning recommends migrating the test client
away from httpx. The application pins the tested dependencies; it does not silently
adopt an untested transport to silence a warning.

Desktop (1440 px) and mobile (390 px) screenshots were inspected. Layout, status
labels, source controls, keyboard focus and dialog actions were checked. The mobile
navigation is horizontally scrollable. No external images/fonts or analytics are used.
Screenshots and Playwright traces live under ignored data/test-results paths.

## Live checks are separate evidence

Actual supported source results and access limitations are in
[SOURCE_POLICY](SOURCE_POLICY.md), with measured cycle/query results in
[BENCHMARKS](BENCHMARKS.md). Fixtures are not proof of current remote access.
No live Ollama model, OS startup installation, Linux service, or macOS LaunchAgent
was tested/installed. Native Windows startup and production dashboard are tested.

Tests do not establish universal natural-language accuracy. Conservative unknowns
and source-specific fixtures should be extended before promoting additional claim
patterns or adding a provider's regional/program-specific terms.
