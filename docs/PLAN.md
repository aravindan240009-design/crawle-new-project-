# Plan

The dynamic master prompt requested on 2026-10-09 supersedes the old fixed-source roadmap.

| ID | Acceptance | Status |
|---|---|---|
| D1 | Durable frontier, campaign leases, incremental publication, replayable events | Implemented and tested |
| D2 | Nonseed search, recursive discovery, Crawlee orchestration, taxonomy/budgets | Implemented; real SearXNG/GitHub and broad category collection checked |
| D3 | Live discovery UI, campaign controls, capability and coverage reporting | Implemented; browser/replay/mobile tests passed |
| D4 | Guarded browser/media, optional Tamil/English OCR/ASR, platform capability research | Implemented; browser/caption/missing-runtime fixtures passed; OCR/ASR models and Instagram authorization unavailable |
| D5 | Repository licensing/trends, alert rules and quiet hours | Implemented and tested, including releases/corrections/deadline rules |
| D6 | Dynamic acceptance, live validation, docs/license audit | Passed for available capabilities; limits documented |
| D7 | Extraction quality evaluation and optional runtime validation | Next refinement; explicit model opt-in required |

Next task D7: curate a small held-out public offer set across Food/Travel/Shopping
and open source; measure actionable-offer precision separately from page-fetch
success, preserving field-level evidence and unknowns. Improve domain-specific
extraction only when fixtures demonstrate a real gap. No internet-wide recall claim.
Optional OCR/ASR quality work requires separately chosen, licensed local models;
do not auto-download them. Instagram needs an authorized supported connector and
must remain visibly unavailable until one is actually implemented and validated.
See README.md for commands and SOURCE_CAPABILITIES for exact capability limits.
