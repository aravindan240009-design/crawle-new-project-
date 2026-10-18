# Source capabilities

Checked 2026-10-09. A fixture validates behavior, not platform reachability.

| Capability | Current evidence / limitation |
|---|---|
| Local SearXNG | Running on 127.0.0.1:8088; real Chennai workshop query returned 27 results. One engine rate-limited. Container trusts existing Windows root CAs; TLS stays enabled. |
| Dynamic web pipeline | Real two-query campaign queued 61 URLs, fetched five nonseed pages and observed six repositories in 40.187 seconds. Further Food/Shopping/Travel campaigns completed 3/6 and 2/3 page fetches, with access/DNS/timeout failures recorded. Counts are discoveries, not verified offers. |
| GitHub repositories | Public unauthenticated search and metadata succeeded; no code executed. API-declared license is separate from legal review. Growth requires two observations at least one hour apart. |
| Unknown-domain crawling | Deterministic tests cover search → provisional → fetch → evidence → searchable result → revisit due. No manual seed edit. |
| Feeds/sitemaps/links | Bounded relevant links and XML feed/sitemap links discovered; robots sitemap URLs enter the same safe queue. Live route coverage varies. |
| Browser | Chromium installed; real browser fixture executes JavaScript while private HTTP subrequests are rejected. Live challenge bypass is not provided. |
| Captions/direct media | Direct permitted files only, 2 MB limit. Caption → extraction subprocess → timestamped live evidence/digest tested. Optional video OCR samples at most six resized frames over 120 seconds. Streaming manifests disabled. |
| OCR | Optional Tesseract. English/Tamil data must be installed; neither runtime nor accuracy validated locally. |
| ASR | Optional faster-whisper + local model + ffmpeg. No model downloaded; language capability depends on selected model. No live transcription claim. |
| Instagram | No authorized connector configured or implemented. No global reel stream, consumer-account crawling, personal-cookie import or login bypass. |
| Issuer identity | Reciprocal cross-domain profile/directory links plus matching public name, phone and locality support the issuer-posted label. Fixture-tested, not live merchant-validated. Ambiguous identities remain unverified. |
| Local alerts | In-app rules, provisional opt-in, cooldowns and IST quiet hours. No external notification destination used. |

The Meta-published API documentation distinguishes professional-account access and
does not provide unrestricted consumer-account discovery. Actual supported scopes,
permissions and quotas must be assessed for an authorized integration before enabling
it. [Meta API documentation](https://www.postman.com/meta/instagram/documentation/6yqw8pt/instagram-api?entity=request-23987686-af579d08-121e-4897-8f45-5fd41ace49df).

Tesseract's official data list includes English and Tamil. This establishes available
language packs, not extraction quality on shop signs. [Tesseract data](https://github.com/tesseract-ocr/tessdoc/blob/main/Data-Files.md).
Faster-whisper supports language tokens including Tamil in multilingual models; a
particular local model still requires testing. [Tokenizer implementation](https://github.com/SYSTRAN/faster-whisper/blob/master/faster_whisper/tokenizer.py).

Near Chennai filtering uses source-declared coordinates, excluding unknown points.
Explicit ISO booking/travel date ranges retain unknown cutoff/timezone; ambiguous
natural-language dates are not guessed. Completed activity/cache retention is
user-controlled; immutable published evidence stays attached to archived versions.
Remaining limits: no live OCR/ASR language-quality or merchant-identity validation,
no authorized Instagram connector, no exhaustive per-category discovery/recall claim.
Frame OCR requires installed language data; that optional path is implemented but
not live-validated here. See PLAN/PROGRESS; README is the command reference.
