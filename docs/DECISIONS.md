# Durable decisions

## Dynamic revision, 2026-10-09

The user's new master prompt replaces fixed-source/complete-scan gating. Keep the
working app and immutable archives; add persistent discovery and per-item live
publication. Crawl permission and issuer trust are separate. Unknown domains enter
the safe frontier automatically without being added to the official-domain registry.

| Upstream | Decision and reason |
|---|---|
| [SearXNG](https://github.com/searxng/searxng) | Adopt separate local service, pinned image digest; AGPL-3.0 upstream, no code vendored. JSON API and real engines validated; rate limits/errors remain visible. |
| [Crawlee Python](https://github.com/apify/crawlee-python) | Adopt 1.10.4 BasicCrawler, Apache-2.0; custom pinned transport preserves SSRF controls. Disable blocked retries/session rotation/evasion. SQLite remains durable authority. |
| [Crawl4AI](https://github.com/unclecode/crawl4ai) | Reference only; a second overlapping crawler adds cost without a demonstrated gap. |
| [Scrapy](https://github.com/scrapy/scrapy) | Reference only; avoid duplicate scheduling/transport infrastructure. |
| [RSSHub](https://github.com/DIYgod/RSSHub) | Defer optional AGPL service; individual route access must be validated. Native discovered feeds work without it. |
| [Folo](https://github.com/RSSNext/Folo) | UX reference only; no account/application stack dependency. |
| [changedetection.io](https://github.com/dgtlmoon/changedetection.io) | Reference revisit/diff patterns; existing immutable versions and durable frontier cover baseline. |
| [Vane](https://github.com/ItzCrazyKns/Vane) | Reference cited-result UX; do not introduce mandatory model inference. |
| [yt-dlp](https://github.com/yt-dlp/yt-dlp) | Do not enable generic remote downloader: it can open unchecked manifest/segment URLs. Safe direct-media fetch is the supported baseline. |
| [faster-whisper](https://github.com/SYSTRAN/faster-whisper) | Optional local ASR adapter, MIT code; selected model license/capability requires separate review. No model downloaded. |
| [PaddleOCR](https://github.com/PaddlePaddle/PaddleOCR) | Evaluated as alternative; use optional Tesseract for explicit English/Tamil packs and simpler native execution. No OCR runtime silently installed. |
| [Apprise](https://github.com/caronc/apprise) | Defer external destinations; local rule alerts are complete without sending messages. |

[Crawlee API](https://crawlee.dev/python/api/class/BasicCrawler),
[SearXNG JSON API](https://docs.searxng.org/dev/search_api.html) and
[container setup](https://docs.searxng.org/admin/installation-docker.html) informed
integration. License metadata for actually installed Python packages is recorded
in PYTHON_LICENSES.md. Service/model notices remain their upstream responsibility
when distributing them; this repository contains configuration, not their source.

The first container search failed TLS validation because the container lacked this
PC's established trust roots. Mirroring Windows ROOT certificates into a read-only
container CA directory fixed it without disabling TLS or changing system trust.
Initial >95% memory handling stopped all discovery. Replaced it with one-task HTTP
dispatch and deferred expensive stages; extreme >99.5% pressure still stops batches.

The earlier decisions below describe the retained baseline where not superseded.

- 2026-10-09: Native Python 3.11 + FastAPI, SQLite WAL, React/TypeScript/Vite. Standard-library scheduler with durable database state avoids a second job store. One API process may own a scheduler; database leases arbitrate all triggers.
- No Codex setting override is needed; `.codex/config.toml` contains comments only. No trust or global configuration changes.
- Conservative extraction: keep raw claims as leads unless exact official evidence supports them. Unknown geographic or personal eligibility is visible, never inferred from access.
- Preserve unrelated Desktop Git changes. All project files remain scoped to crawleee.
- Current package metadata was resolved and locked on 2026-10-09. Runtime pins in
  requirements.lock and frontend/package-lock.json; license reports are generated
  from installed metadata. Node 24.15.0 satisfies the tested Vite/TypeScript toolchain.
- Use the [httpcore public network-backend interface](https://www.encode.io/httpcore/network-backends/)
  to validate DNS and connect to literal public addresses while preserving original
  TLS host verification. No unchecked second DNS lookup, proxy or redirect shortcut.
- pip's initial default CA path failed here. Its OS truststore feature and Node's
  NODE_USE_SYSTEM_CA resolved installation without disabling certificate checks.
- Google Cloud's marketing page exceeded the 2 MB cap. Switched to the official
  Free Program documentation rather than enlarging the cap. The MLH legacy .io
  season page redirects to official .com; current-season link and structured event
  cards were inspected before approving the domain/strategy.
- Offline fixture scans intentionally delay 2.5 seconds only in demo mode so browser
  tests can observe progress; real runs report actual measured work and no fake ETA.
- The optional model is strictly extractive and cannot omit conditions. This is
  deliberately less flexible than generative paraphrasing and offers no baseline
  speed/accuracy promise. See README for limits and separately trusted endpoint.
- User requested continued implementation and additional features on 2026-10-09.
  Added a local publication-only digest, personal application tracker, reminder
  alerts and downloadable calendar. No messaging, calendar connector or account
  dependency was introduced. New attachment f5c41d5c was empty on disk; original
  saved PRODUCT_SPEC remains authoritative.
