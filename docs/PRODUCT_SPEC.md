# Dynamic Opportunity Radar — Single Codex Master Prompt

Build this project in the current workspace. Deliver a working application, not just a plan, simulated scan, hardcoded offer feed, or collection of disconnected repositories. Make routine implementation decisions independently; inspect existing code and instructions and preserve unrelated work. This specification replaces the previous Global Opportunity Radar startup specification. Do not paste both into the project as competing instructions.

## 1. Revised objective and precedence

I live in Chennai, India. I miss offers because a new startup, small shop, restaurant, travel operator, developer, or creator may announce something only on a website, public post, reel, video, community, or GitHub repository I have never seen. I want automatic ongoing discovery, not merely monitoring a preselected company list or searching “top offers” on demand.

Build a local-first, dynamically expanding opportunity search and monitoring system. Discover previously unknown entities and sources, collect accessible original evidence, extract actionable offers/releases, explain eligibility and uncertainty, and notify me. Cover global online opportunities and local physical opportunities, with India/Chennai as default relevance preferences rather than a global crawling prohibition.

The new requirements explicitly supersede earlier decisions:

- Fixed-source-only operation is unacceptable. Seed sources are bootstrapping aids, never the discovery boundary.
- The UI must show actual fetch/search/browser/media processing events as they happen. No animated fake terminal, generated scanning URLs, fabricated counters, or timer-based success messages.
- Live results are now required. Persist and show newly extracted candidates immediately with provisional status; upgrade them as evidence arrives. Do not wait for an entire crawl to finish before showing discoveries or verified results.
- Continuous discovery is a primary mode, alongside manual and daily campaigns. An open-ended crawler never reaches “100% of the internet.” Use bounded campaigns and persistent background discovery.
- Support food, travel, local shops, shopping, software, AI, education, events, and open-source discoveries from the beginning of the taxonomy. Do not restrict discovery to AI/cloud brands.
- Keep the earlier essentials: no dashboard login for localhost use, no mandatory paid API/model/cloud, concise summaries, direct original links, extensive frontend filters, history, source health, bookmarks, scheduling, and modest local-PC resource use.
- Keep the credit-conscious development workflow in section 16. These files reduce repeated work; they do not make Codex usage free or unlimited.

The ambition is to be more useful than an occasional chatbot/search session for this specific ongoing discovery problem: continuous monitoring, local relevance, media extraction, persistent history, and evidence-based alerts. Do not claim superiority to ChatGPT, Perplexity, or any search engine without a fair measured comparison.

## 2. Feasibility contract: broad automatic discovery with visible gaps

Implement useful broad discovery rather than promising the impossible. No local free crawler can index every website, see every public or private reel, bypass platform restrictions, identify an unlinked/unindexed announcement, or guarantee every offer worldwide. A platform may expose content in its app that it does not expose to search engines or APIs. A media downloader cannot discover a URL it does not know.

The system must distinguish: discoverability, permitted accessibility, successful retrieval, extraction quality, issuer identity, offer validity, geographic availability, and personal eligibility. Failure at one stage must remain visible. An HTTP 200, working website, popular account, or confident model answer does not prove the offer.

No dashboard account is required. Optional external platform credentials/permissions may be needed for a particular connector; document them honestly. An unavailable social connector must not disable general web discovery, and a functioning general web crawler must not imply Instagram coverage.

Do not bypass logins, CAPTCHAs, access controls, private accounts, robots policies, rate limits, or platform restrictions. Disable anti-detection/stealth and proxy-rotation-for-evasion features even if dependencies offer them. Ordinary browser rendering for permitted dynamic pages is supported; defeating restrictions is not.

## 3. Architecture: discover, investigate, monitor, and learn

Use a modular local application with a backend API, durable workers, database/search index, bounded browser/media workers, and React/TypeScript frontend. Preferred baseline: Python/FastAPI, SQLite WAL with migrations and FTS5, React/Vite, and persistent job/event storage. A local SearXNG sidecar supplies federated search where its enabled engines work. Choose Crawlee Python with Playwright as the primary crawling layer; retain httpx/readability extraction for low-cost fetches. Evaluate Crawl4AI as an alternative or narrowly justified extraction adapter, not a second overlapping crawler installed by default. Use native setup plus optional Compose/WSL instructions where sidecars require it.

Do not add Kafka, Kubernetes, a vector database, multiple workflow engines, or a distributed cluster before local measurements justify them. Put worker/queue/storage interfaces behind clear boundaries so scaling remains possible. Do not present a single PC as internet-scale infrastructure.

Implement four cooperating loops:

1. DISCOVER: expand search queries, search multiple enabled source families, inspect feeds/directories/sitemaps and relevant links, discover new domains/accounts/repositories, and add candidates to a durable frontier.
2. INVESTIGATE: safely fetch/render candidates, extract text and relevant media, identify issuer and original announcement, normalize claims, deduplicate, and assess applicability/evidence.
3. MONITOR: revisit useful sources and active offers with adaptive cadence; detect changes, expiries, releases, and withdrawals; create alerts.
4. IMPROVE COVERAGE: measure yield, missed categories/locations/languages, discovery novelty, blocked connectors, and resource costs. Allocate future exploration with bounded transparent rules rather than an expensive autonomous LLM loop.

Persist provenance edges such as query → search result → post → business/profile → original announcement → offer version. Use relational edges; a separate graph database is unnecessary initially. Every result should answer “How did you find this?” and “What supports this claim?”

## 4. Dynamic discovery engine — core deliverable

Implement a real discovery scheduler and frontier. Queries should combine category, offer intent, language, location, recency, and discovery channel. Templates must cover more than famous brands and “best deals.” Examples include opening/anniversary offers, introductory promotions, free entry, buy-one-get-one, flash sales, coupons, limited free credits, newly open-sourced tools, release announcements, and local dining/travel offers. Preserve Tamil and English queries and common Tamil transliterations for Chennai; allow other languages and regions.

Generate bounded candidate queries deterministically. Optional local-model expansion may suggest terms but cannot fabricate discovered entities or become necessary for each query. Rotate recent-time windows, locations, neighborhoods, lesser-known providers, categories, and synonyms. Deduplicate query signatures and enforce query/engine quotas. Global mode rotates regions/languages; it is not an infinite country × keyword × time Cartesian product.

Discover from:

- Federated web/news/video search with independent provider adapters and visible per-engine outcomes.
- Official and newly found websites, public blogs, directories, public local-business/event listings where permitted.
- Automatically discovered RSS/Atom links, sitemaps/sitemap indexes, and bounded relevant internal/external links.
- Public communities, newsletters with public archives, discussion sites, and public social/video discovery endpoints where allowed.
- GitHub search, repository topics, public release feeds, and permitted ecosystem announcement feeds.
- Optional Common Crawl index lookup for historical URL discovery only. Always fetch the current original source before asserting a current offer; an archived index is not a live feed.
- User-supplied public URLs/media as a supplemental path, never a substitute for automatic discovery.

Each search result stores query, engine, rank, observed time, URL, and snippet. A snippet is a lead, not verified offer evidence. Search absence is not proof no offer exists. If SearXNG or all engines fail, report degraded discovery; do not quietly replace search with canned results or label fixed feeds as broad discovery. Avoid dependence on arbitrary public SearXNG instances; provide local setup/health checks.

New domains must be crawlable automatically after URL/access/security checks within small budgets; do not require manual approval for every ordinary public domain. Separately assess whether the entity is the genuine issuer. Crawling permission is not source trust. Auto-discovered sources must not become verified merely by being in the registry.

Persist frontier fields: canonical URL, discovery parent, entity/category/region/language, priority, crawl depth, policy status, first/last discovery, next due, attempt count, lease, last status, and budget usage. Enforce URL/domain/page/depth/time/media limits, fairness, deduplication, and trap detection for calendars, faceted navigation, session URLs, infinite scrolling, and endless generated pages.

Reserve configurable exploration capacity for unknown/small sources—start with an explicitly provisional 20% budget—and monitor known useful sources with the remainder. Avoid popularity-only ranking. Use freshness, novelty, local relevance, underrepresented categories, issuer evidence, and observed useful yield. Do not permanently suppress a low-volume shop just because it rarely posts.

## 5. Reels, video, images, and small-shop coverage

This is an essential product pathway, not a decorative social icon:

Public discovery/API/indexed search/accessible profile → known post/reel URL → permitted metadata/caption retrieval → permitted media or source-frame access → local transcription/OCR → business/offer/date/location extraction → issuer/evidence assessment → live result and alert.

Separate discovery adapters from media extraction adapters. Discover newly encountered accounts through search, local public directories, relevant public posts/links, and permitted platform discovery. Monitor accessible discovered accounts afterward. Account monitoring alone must not be marketed as discovering all new accounts.

For Instagram, investigate current official API access, account/app requirements, supported discovery scopes, and limits before implementation. Do not assume any API returns the global reels stream. Do not hardcode unofficial private endpoints, import personal browser cookies automatically, or ship a connector as working when it only returns fixtures. The core app needs no login; a separately configured official integration may need authorization. Keep unavailable capabilities visibly disabled with the exact reason.

For permitted public media, evaluate yt-dlp as a retrieval adapter, faster-whisper for speech transcription, and a licensed OCR engine such as PaddleOCR or a suitable alternative for on-screen text. Confirm actual Tamil/English support for the selected model; multilingual branding alone is insufficient. Install/download models only through documented opt-in setup. Run OCR/ASR locally with bounded duration, frames, resolution, threads, concurrency, storage, and timeouts. First use caption/structured text; process media when missing fields justify the cost. Media processing is core but may require enabled optional runtime dependencies.

Retain source URL/post ID, original publication time when available, retrieval time, transcript language, relevant timestamped transcript spans, OCR frame timestamps, quoted prices/dates/conditions, and extraction confidence. Do not fabricate subtitles or infer prices from unclear audio. Preserve original text beside translations. Reposts inherit neither freshness nor issuer authority automatically. “Today only” is unresolved without a credible post date and relevant timezone.

Small shops may have no website. Accept evidence from an issuer's public social announcement when identity is supported, while clearly labeling “Issuer-posted; redemption not independently confirmed.” Link website/profile cross-references, consistent business name/location, established public contact identity, and other supporting sources when available. Do not demand a paid verification badge or registration document. Name/handle similarity alone is not enough. If identity or conditions are unclear, show an unverified lead in its own filterable state rather than discarding it or calling it verified.

Never auto-message a shop, call, reserve, buy, or redeem. Verification here means documenting accessible evidence and limitations, not pretending to have confirmed stock or availability with the merchant.

## 6. GitHub and open-source opportunity radar

Dynamically search new and recently updated repositories by topics, languages, creation/update windows, keywords, and relevant use cases. Discover public repositories outside an initial list and monitor releases after discovery. Respect current GitHub quotas, incomplete-results indicators, search result caps, pagination, and Retry-After/reset information; implement bounded query partitioning rather than claiming exhaustive enumeration. Optional minimally scoped credentials can improve permitted access, but anonymous baseline limitations must remain visible.

Record repository/owner identity, description, direct URL, topics/language, creation/update/release dates, archived/fork status, license file/SPDX when identifiable, documentation/demo links, installation/hardware needs if documented, and observed popularity history. A public repository without a license is not automatically open-source. Distinguish OSI-style open source, source-available, open weights, no clear license, free self-hosted software, and hosted plans requiring payment. “Free code” does not mean free cloud/API/GPU operation.

Offer “New and undiscovered” separately from “Trending among tracked repositories.” Compute a transparent trend score from actual timestamped observations, such as star deltas per elapsed day, release recency, and relevant activity. One star count is not velocity. Do not invent a GitHub Trending API or represent sampled growth as all-GitHub rankings. Explain ranking factors and allow low-star/new-repository filters. Stars are neither security review nor proof of quality.

Notify for matching new repositories/releases and significant changes without alerting on every commit. Never execute, pip-install, npm-install, or run discovered repositories automatically to assess them. Development dependencies selected deliberately are separate from arbitrary discovered code.

## 7. Categories, offer schema, and evidence

Taxonomy must include food/restaurants/cafes; travel/flights/hotels/transport; shopping/electronics/clothing; local services; entertainment/events; courses/scholarships; internships/jobs/fellowships; hackathons/grants/startups; AI/cloud/software/developer tools; open-source releases. Keep informational news separate from actionable opportunities.

Offer types: free, limited free tier, free trial, credits, percentage/fixed discount, coupon, BOGO, cashback, giveaway, admission/application opportunity, release, and news. Store distinctions such as minimum spend, bank/card condition, automatic renewal, usage caps, eligibility, new-customer limitation, application approval, stock uncertainty, and taxes/fees. Do not equate cashback with an immediate price reduction.

Persist stable entity/offer IDs; original source and discovery paths; versioned claims and evidence; category/type/tags; provider; headline; 2–3-line faithful summary; benefit/value/currency; official/original/claim/terms links; location/coordinates if supported; online/offline; travel origin/destination and booking/travel windows; validity dates/timezone/precision; issuer confidence; verification status; geographic and personal eligibility separately; first seen, source publication, fetched, checked and next-check times; lifecycle; bookmark/dismiss/notes.

Unknown fields remain null/unknown. Explain “India eligible,” “Likely eligible,” “Unclear,” and “Not eligible” with evidence. A global offer can be geographically usable but personally conditional. Default to Chennai/India relevance while allowing worldwide exploration, travel destinations, remote participation, and radius filters. Do not silently drop uncertain or nonlocal items at collection.

Evidence should be claim-specific: original URL, concise excerpt or media timestamp, retrieval time, source hash, issuer assessment, and supported field. Distinguish issuer-confirmed details, third-party report, inference, and missing details. Model summaries never establish truth. Use deterministic templates by default, optional local structured extraction/summarization, schema validation, numeric/date checks, and fallbacks.

## 8. Genuine live UI and event architecture

Create a polished, accessible, responsive dashboard with real-time operational visibility, not a chatbot shell. Main views: Live Discovery, Offers, Near Me, Reels/Media Leads, Open Source, Alerts, Campaigns, Sources/Coverage, and Settings. Consolidate navigation if it improves usability without removing capabilities.

The live screen shows running campaign/worker health, active queries, engine, current domain/URL, actual stage, queue size, fetched pages, new entities, candidates, verified/uncertain results, blocks/errors, bytes/time/resources, last event and data timestamps. Display statuses generated by backend actions, including queued, search_started/completed/failed, fetch_started/completed, unchanged_304, browser_rendered, media_pending/transcribing/OCR, extraction_completed, evidence_checked, offer_created/updated, alert_created, rate_limited, blocked, retry_scheduled, paused, canceled, and campaign_finished.

Implement durable ordered events with event ID, run/campaign ID, task ID, timestamp, stage, resource reference, safe metadata, result/error code, and real duration. Persist business state plus its event/outbox atomically, publish after commit, stream through SSE or an equivalent resumable channel, and support cursor replay/reconnect. Client deduplicates by event ID. Never emit a completion before the underlying operation succeeds. A heartbeat proves worker connectivity, not a fetched page. Aggregate counters from recorded events/state, not frontend random/timer increments.

Support pause/resume/cancel with clear behavior for in-flight requests. Cancellation must stop new work promptly and leave already committed results intact. Reopening the UI should not restart the crawler or duplicate jobs. Show historical event playback explicitly as replay, never LIVE.

Show provisional discoveries immediately in a separate lane; verified/issuer-supported items can join the main results as their individual version transaction commits. Retain previous good versions/history on failed checks. A later contradiction changes status and can retract/correct an alert. Snapshot/export at campaign boundaries is optional convenience, not a prerequisite for live publication. This intentionally replaces the old batch-only rule.

Provide an optional real browser-worker preview: current public page URL, actual time-stamped screenshot after navigation/render, and stage. Capture at a bounded frequency and label the last-captured time; a screenshot is not a continuous video. Do not capture authenticated personal sessions or secrets. HTTP/API jobs correctly show request metadata instead of a fake browser. Never silently substitute mock screenshots. Keep this preview off when resources are constrained.

No global completion percentage. Bounded campaigns may show completed queued work with a changing total clearly labeled, plus discovered/pending counts and stop reason: time/page/query budget, frontier exhausted for this campaign, paused, canceled, or failure. Show stale/offline and event-disconnected states distinctly.

## 9. Filters, search, ranking, and alerts

All preferences must be manageable in the frontend; changing display filters must not rerun collection. Implement paginated indexed search, URL/saved-view state, consistent export predicates, and responsive sorting.

Filters: category/subcategory; free/trial/credits/discount/BOGO/cashback; benefit/price/discount range; minimum spend; card/account/new-customer/student/startup requirement; country/state/city/neighborhood/radius; online/offline; travel origin/destination; booking/stay/travel dates; language; source channel; video/image/text; original vs repost; newly discovered business; evidence/issuer confidence; verification and eligibility; freshness; first discovered/published date; expiring window; active/upcoming/expired/withdrawn; bookmarked/dismissed; included/excluded merchants/keywords. Unknown fields must not satisfy precise known-value filters.

GitHub-specific filters: topic, language, license class, repository age, observed star range/growth, release recency, archived/fork status, self-hosted/cloud dependency, documented hardware requirement, and new vs tracked-trending.

Provide ordinary search plus optional natural-language-to-filter translation with a visible editable filter representation. Do not require an LLM for core search. Ranking should explain freshness, relevance, novelty, evidence, and deadline; give small/new entities an exploration path. Do not call “highest discount” “best value” without enough cost information.

In-app alerts required; optional user-enabled sound, browser/OS notifications, and configurable external adapters such as Apprise. Do not connect or send to external channels without user setup. Browser notification delivery may depend on page/browser state; background desktop delivery requires a running supported service. Implement quiet hours, saved-search rules, per-category thresholds, urgency/expiry windows, deduplication, cooldowns, read/resolved state, and daily digest. Default alerts prioritize supported, relevant offers; provisional alerts are explicit opt-in. No alerts for every fetch or repeated identical post.

## 10. Reliability, freshness, and resource budgets

Continuous means persistent scheduled work while the local machine is available, not uncontrolled requests. Manual, daily, and continuous modes share one durable task/lease mechanism so workers do not overlap jobs. Recover expired leases after crashes. Use bounded retries with backoff/jitter, circuit breakers, domain fairness, policy checks, and concurrency limits. Persist schedules and coalesce missed runs after sleep instead of creating a catch-up storm.

Offer low-resource, balanced, and deep-discovery profiles with editable query/page/host/browser/media/time/disk budgets. Present their scope and last measured throughput. Start conservatively and tune on actual hardware. No guaranteed scan duration, under-one-minute discovery, or unlimited worldwide crawl.

Keep conditional GET, cache validators and content hashes: removing caching wastes bandwidth and processing. “Live” means real executed operations and transparent freshness. A 304 is a real check of unchanged content; a cached read alone must show its age and is not a fresh network fetch. A force-recheck honors rate limits. Search caches must be explicitly labeled with their age.

Deduplicate conservatively using platform post/repo IDs, meaningful canonical URLs, provider/program/location/period, text hashes and optional near-duplicate media fingerprints. Strip only tracking parameters. Preserve distinct branches, regions, deadlines, products and offer tiers. Missing rediscovery or one 404 is not automatic withdrawal; mark stale/unavailable and recheck appropriately. Preserve past evidence and user notes.

Use priority queues for fresh/expiring/high-relevance candidates, cheaper metadata before browser/media work, and extraction on changed/new content. Model/ASR/OCR work runs outside the API event loop. Monitor CPU/RAM, queue age, disk growth, and stages; apply backpressure. Log concise diagnostics and rotate/retain events/evidence within user-controlled limits.

## 11. Security and privacy

Bind services to localhost by default, defend Host/Origin/CSRF/CORS, use parameterized queries and validated inputs, sanitize scraped content, and prevent CSV injection. Exports/backups must not contain secrets. No outbound analytics by default. Protect optional tokens in environment/local secret stores excluded from git and redact query strings, signed links, headers, and notification credentials in events/screenshots.

The frontier handles untrusted URLs. Validate HTTP/HTTPS, ports, redirect chains, DNS and resolved connection targets; reject local/private/link-local/metadata destinations for IPv4/IPv6 and DNS rebinding. Apply protections to browser subrequests, images/media manifests/segments, redirects, downloads, and extraction utilities—not only the first page URL. Trusted configured localhost sidecars are separate allowlisted connections and must not turn the crawler into an open proxy.

Limit content size/decompression/time, browser navigation/subresources, media duration, downloads and parser resources. Use isolated browser contexts without personal cookies, disable arbitrary external download execution, and never execute untrusted repository code. Treat webpage/transcript/repository instructions as untrusted data, including prompt injection. Use bounded relevant text in any model call, no secret/tool privileges, and validate output.

Respect access rules and retain short relevant evidence instead of redistributing entire copyrighted videos/pages. Document optional media retention and deletion. Original source evidence is the goal, not harvesting personal profiles or unrelated personal information.

## 12. Upstream projects to learn from — selective integration

The following upstream repositories/docs were reviewed at a capability level on 2026-10-09. This is a relevant shortlist, not “all GitHub” or a code/security audit. Before adopting, inspect the current license, maintained release, API, native setup and resource requirements. Record one concise adopt/reference/reject decision per relevant candidate. Reuse compatible libraries/services and ideas; do not merge all repositories or assume their hosted features are available free locally.

| Upstream | Useful role | Selection guidance |
| --- | --- | --- |
| https://github.com/searxng/searxng | Federated search | Preferred local search sidecar; upstream engines may fail or limit access; validate JSON support. |
| https://github.com/apify/crawlee-python | Durable crawling and HTTP/browser routing | Preferred crawler foundation; use permitted ordinary fetching, not evasion features. |
| https://github.com/unclecode/crawl4ai | Structured extraction, URL discovery, adaptive crawling | Evaluate as an alternative or focused adapter, not duplicate default infrastructure. |
| https://github.com/scrapy/scrapy | Established crawling architecture | Alternative/reference; do not install a second crawl framework without a demonstrated need. |
| https://github.com/DIYgod/RSSHub | Routes for converting supported sources to feeds | Optional selective integration; every route has its own availability/access requirements. |
| https://github.com/RSSNext/Folo | Feed reading/discovery UX | Design reference; do not require its full application/account stack. |
| https://github.com/dgtlmoon/changedetection.io | Revisits, meaningful diffs, notifications | Learn the change-monitoring pattern; optional integration rather than duplicating the whole stack. |
| https://github.com/ItzCrazyKns/Vane | Cited search UX and federated retrieval | Former Perplexica URL redirects here; reference, not a guarantee of superior search or free model inference. |
| https://github.com/yt-dlp/yt-dlp | Permitted media URL retrieval | Retrieval after discovery, not a universal reel search engine; source support can break. |
| https://github.com/SYSTRAN/faster-whisper | Local audio transcription | Opt-in media dependency; benchmark selected model on actual CPU/GPU. |
| https://github.com/PaddlePaddle/PaddleOCR | Extract offer text from images/frames | Select and test language/model support; separate code and model license review. |
| https://github.com/caronc/apprise | Optional notification adapters | Keep in-app alerts independent and destinations opt-in. |

Additional primary documentation:

- https://docs.searxng.org/dev/search_api.html
- https://docs.github.com/en/rest/search/search
- https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api
- https://index.commoncrawl.org/
- https://developers.facebook.com/documentation/instagram-platform/instagram-api-with-facebook-login/hashtag-search
- https://developers.facebook.com/documentation/instagram-platform/instagram-api-with-facebook-login/business-discovery

Meta pages were discoverable in search but direct retrieval was unavailable during preparation; recheck official current access requirements during implementation. Do not bake an exact historical quota into architecture. Use observed limits and configurable adapter policies. SearXNG and RSSHub report AGPL licensing in their reviewed repositories; preserve required notices and assess license obligations before reuse/distribution. Open-source availability does not authorize scraping a third-party platform.

## 13. Persistence, APIs, and deployment

Use indexed migrations for campaigns/jobs/frontier, queries/search hits, sources/entities/identity evidence, offer candidates/versions/claims/evidence, media jobs, repository observations, event outbox, alert rules/deliveries, schedules, user state, settings and cache. Consolidate where sensible. Retain immutable evidence/version references and stable IDs for notes/bookmarks. Small batches avoid SQLite contention; serialize writes as needed and measure before changing databases.

Provide typed validated endpoints for campaigns start/status/pause/resume/cancel, SSE/replay, offers/detail/history/search/filter/export, sources/capabilities/health, media processing status, repository discovery/trends, alert rules/state, settings and schedules. A public lead-submission endpoint must enqueue through the same safe pipeline, not fetch arbitrary URLs synchronously. No arbitrary script-execution API.

Provide repeatable Windows-first native startup and backend-served built frontend, Linux guidance, optional WSL/Compose for sidecars, locked dependencies, .env.example, health checks, headless CLI and graceful shutdown. Show capabilities at startup: search online/degraded, browser installed/missing, media enabled/missing model, platform connector authorized/unavailable, notifications enabled/disabled. Do not auto-enable OS startup or change sleep settings; document opt-in installation/uninstallation. Explain that shutdown/sleep/offline time creates coverage gaps.

## 14. Acceptance tests that prove the revised product

Use deterministic offline/local test servers under an explicit test-only private-network allowance that cannot affect production URL policy. Keep live smoke checks small, permitted and labeled. Required tests:

1. UNKNOWN SOURCE: a search adapter returns a domain/business absent from seed config; it enters the frontier, is fetched, produces a candidate/evidence, becomes searchable and is scheduled for recheck without hand-editing a source list.
2. SMALL SHOP: an issuer-linked public post with no website yields a correctly labeled offer; ambiguous account identity stays unverified. Test branch/location and old repost handling.
3. REAL-TIME: a deliberately delayed fixture fetch emits started before completion; the UI shows the real job; successful completion appears only afterward. Disconnect/reconnect replays missing events without duplicates. Replay is labeled.
4. MEDIA: permitted fixture video/image contains an offer in caption/OCR/audio; record relevant timestamped evidence, distinguish unknown words/dates, and show exact disabled reason if runtime model support is absent. Test selected Tamil/English capability rather than assuming it.
5. RESTRICTED SOCIAL: login/CAPTCHA/API restriction yields blocked/authorization-required, not an empty-success or fake coverage result. Other discovery continues.
6. LIVE PUBLICATION: candidate → supported or contradicted versions update in the UI individually. Failed/canceled jobs preserve prior committed evidence. Correct or retract stale alerts when necessary.
7. GITHUB: discover a nonseed repo; verify license classification; observe two timed popularity snapshots before computing growth; handle missing license, forks, archive status, incomplete results and quotas.
8. BROAD COVERAGE: demonstrate food, travel, local shopping, and open-source discovery through the same real pipeline; no category may be represented solely by static sample cards.
9. FILTERS/ALERTS: all meaningful controls work; unknowns behave correctly; saved-search alerts deduplicate; quiet hours and expiry logic work; exports match filters; no external messages without configured opt-in.
10. RELIABILITY/SECURITY: lease recovery, duplicate scheduling, throttling, budgets, crawler traps, no-result vs failure, stale evidence, SSRF including browser/media subrequests, injection and secret redaction.

An offline fixture proves behavior, not current platform reachability. Record which live adapters were tested and which remain unavailable. Never claim the Instagram discovery goal is fully delivered if only manual URL imports work. Finish all implementable work and clearly list connector limitations rather than disguising them as success.

## 15. Quality and realistic comparison

Measure known-source vs novel-source yields, unique relevant offers, small/local entity yield, verified/issuer-supported precision, duplicate rate, source/media extraction failure, per-category/language coverage, query/engine availability, publication-to-discovery lag where publication time is reliable, detection-to-UI/alert delay, CPU/RAM/disk/network consumption, and user relevance feedback.

Use a curated held-out, timestamped opportunity set for recall; never report “internet-wide recall.” Keep fixture benchmarks separate from real discovery evaluation. To compare with a chatbot/search session, use the same geography/time window/access conditions and distinguish a one-time query baseline from a continuous-monitoring baseline. Report supported advantages and misses, not a fabricated “better than everything” score. Benchmark only if an actual comparison can be performed; do not invent competitor results.

## 16. Reduce Codex credits and avoid repeated context

Bootstrap a small durable context set, then code:

- AGENTS.md: roughly 400–600 words of essential rules, live-publication/dynamic-discovery invariants, and selective reading instructions.
- docs/PRODUCT_SPEC.md: this specification once, with section index.
- docs/PROGRESS.md: short current checkpoint—implemented, active task, relevant paths, actual checks, blockers, next action; replace stale notes rather than append a transcript.
- docs/PLAN.md: bounded milestones and acceptance conditions, with detail only for active work.
- docs/DECISIONS.md: durable choices and meaningful failed approaches, including upstream adoption decisions.
- docs/ARCHITECTURE.md and README.md: actual component map and canonical working setup/test commands.
- docs/SOURCE_CAPABILITIES.md and docs/BENCHMARKS.md: current tested adapter limits and real measured results when available.

Use existing valid project conventions. Do not invent codex.json memory semantics. A minimal .codex/config.toml is optional only for supported, necessary client overrides; otherwise inherit settings. Do not change model, effort, global config, approvals or trust to claim credit savings.

On resume, read AGENTS.md/current checkpoint and active plan task, then only relevant source/spec sections. Check actual workspace state before trusting notes. Avoid repository-wide rereads, repeated browsing of unchanged documentation, giant logs, redundant plans, whole-project rewrites, unneeded dependencies and repeated full suites. Use targeted tests for changed behavior, integration gates at milestones, and no fabricated verification. One agent by default; no parallel reviewer swarm. Keep progress updates short and checkpoint at meaningful boundaries, not every tool call. None of this excuses dropping core requirements.

Short continuation prompt to include in README:
“Continue under AGENTS.md. Read docs/PROGRESS.md and the active PLAN task; inspect relevant workspace changes, implement the next ready task using only needed context, run affected checks, and update the checkpoint. Do not restart completed work.”

## 17. Build order and definition of done

First reconcile existing code/docs with the changed requirements. Preserve useful implementation and migrate batch-only publication safely instead of deleting the project. Record that dynamic discovery and live results supersede the former fixed/batch assumptions.

Build in this order:

1. Durable campaign/frontier/event API and live dashboard with real fixture-network events; clearly separate test mode.
2. Working search provider + nonseed domain discovery + HTTP extraction + live candidates/evidence + useful filters. This is the first real vertical slice; a fixed feed demo does not satisfy it.
3. Browser fallback, feed/sitemap/link expansion, location/language exploration and monitoring loop with budgets.
4. Social discovery capability assessment and permitted integrations, local-shop identity evidence, OCR/ASR media path with transparent platform gaps.
5. GitHub dynamic discovery, licensing/trend observations and release alerts.
6. Full filters, saved searches, notifications, schedules, recovery, security, and resource tuning.
7. Real-source smoke checks, accessible UI review, measured quality/coverage, native setup and concise handoff.

Continue through required work; do not stop after writing documents or ask whether to start. Do not claim completion because the first milestone works. If access/hardware blocks one connector, finish independent work and report precisely what remains and why.

Final delivery must contain working source, migrations, dependency locks/licenses, actual setup/start/scan/test commands, local URL, real live-discovery demonstration evidence, tested nonseed discovery path, truthful social/media coverage, actual tests/benchmarks, and the updated next-task checkpoint. Never ship a fake “worldwide live scanner.” Build a measurable, extensible, continuously discovering opportunity radar with original evidence and honest live visibility.

Start now.
