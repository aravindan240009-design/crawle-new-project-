# Current checkpoint

- Updated: 2026-10-09. Dynamic master-prompt upgrade implemented and validated for
  available capabilities. D1-D6 complete for that scope; D7 quality refinement is next
  in PLAN.md. Do not restart bootstrap. User requested the new master prompt and continue.
- Primary modules: discovery_store/search/discovery/api/browser/media/identity/alerts.
  Migrations 004?005 add persistent frontier/campaign generation leases, immediate
  provisional/live versions, transactional ordered events and replay, provenance,
  issuer observations, media jobs, repository observations and quiet-hour alert rules.
- Live UI: Discovery.tsx plus existing cards. Actual activity, pause/resume/cancel,
  persistent queue, coverage/capabilities/media, budget profiles, category fairness,
  provisional/license/media/radius filters, rules, live detail/history/digest updates.
  Known seeds remain optional. Safe public lead submission queues automatically.
- Evidence: unknown domains stay unverified. Reciprocal exact profile/directory URLs,
  matching public name/phone/locality support issuer-posted label, never redemption.
  Branch and repost uncertainty retained. Explicit ISO travel windows preserve unknown
  cutoffs/timezones; INR, BOGO/cashback/coupon and source-declared coordinates supported.
- Guarded browser routes all HTTP through pinned Fetcher, blocks private subrequests,
  uses closed-proxy fallback and no personal cookies/evasion. Direct media cap2MB;
  captions, optional image/frame OCR and local-only ASR run in bounded subprocesses.
  Frame OCR max6 resized frames/120s; ffmpeg forced formats disable external references.
- Final backend suite: **86 passed**, 30.25s; one upstream Starlette deprecation warning.
  Frontend **5 unit passed**, TypeScript/Vite build passed (276.07kB JS/83.52kB gzip).
  **3 browser scenarios passed**, 26.2s, including dynamic pause/replay/rule creation.
  Real desktop/mobile screenshots: no JS errors or horizontal overflow.
  One intermediate targeted failure came from overlapping a frontend rebuild; affected
  test and final full suite passed after build. Do not run static-asset tests during builds.
- Live observations: campaign d2b45a259fa448c096c690b795ebc977,40.187s,2 query responses,
  6 nonseed repos,5 successful page fetches,61 URLs queued. Category-balanced campaign
  396bc17df3e1433096e69e1658e1a605,41.844s,3 queries,2 attempts each Food/Shopping/Travel,
  3 successes/3 HTTP403 or DNS failures,80 URLs queued. Travel follow-up a7c59ef713af44299a75ed64df2fbc9a,
  26.593s,2 successes(Red Taxi/Agoda),1 timeout,13 URLs queued. Counts are not verified offers.
- SearXNG running localhost:8088; real workshop query27 results,one engine rate-limited.
  Docker Desktop started; compose.yaml pins image and loopback port, no restart policy.
  setup-search.ps1 mirrors existing Windows ROOT trust into ignored data/host-ca for
  container TLS; verification remains enabled, no global trust/permission changes.
- Latest verified server restarted at http://127.0.0.1:8765 with schema005 and built UI.
  data/server.pid tracks launcher; scripts/stop.ps1 validates ownership. Schedule remains
  disarmed; no OS startup/wake changes. Backup data/before-dynamic-upgrade.sqlite retained.
- Dependency lock/license report regenerated; pip check passes. README is canonical
  commands; ARCHITECTURE/DECISIONS/TESTING/SOURCE_CAPABILITIES/BENCHMARKS updated.
- Explicit limits: Tesseract/English/Tamil data and Whisper model not installed, no
  OCR/ASR language-quality/live frame-accuracy claim. No authorized Instagram connector
  or global reel discovery. Merchant identity linking is fixture-tested, not live-vetted.
  No exhaustive coverage/precision/recall or chatbot-superiority claim. D7 should evaluate
  held-out real offers before refining extraction; model downloads require explicit opt-in.
- All project work remains uncommitted inside Desktop Git. Unrelated parent work
  preserved. No paid service, external messages, public deployment or model download.
