# Dynamic Opportunity Radar

Build a local opportunity dashboard for India/Chennai, with official evidence,
faithful short summaries, and no mandatory login, paid service, or model.
Persist and publish individual discoveries immediately with provisional status;
retain prior good versions through failed, canceled, and interrupted jobs. The PC must be awake and online
for collection. Never describe configured sources as successfully validated.

## Resume and context

On a fresh session or after lost context, read `docs/PROGRESS.md` and the active
task in `docs/PLAN.md`, then inspect the relevant implementation. Do not repeat
these reads before every edit when their content is already known and unchanged.
Read only the relevant sections of `docs/PRODUCT_SPEC.md` for the feature at hand.
Read `docs/ARCHITECTURE.md` for boundary/schema changes and `docs/DECISIONS.md`
when a previous choice matters. Ordinary documents are not automatically loaded.

Source code and tests establish actual behavior; the product specification is
the authoritative desired behavior. Check progress claims against files and
Git state. Current user requests can change requirements: record material
changes while preserving unrelated requirements and higher-priority instructions.
Keep one current checkpoint in PROGRESS after a meaningful implementation chunk,
before an intentional stop, and before compaction when possible. Interruptions
cannot always be anticipated. Do not create duplicate memory or handoff files.

## Implementation rules

Use a single agent unless explicitly requested otherwise. Continue routine
authorized implementation without repeated permission questions. Do not add
paid services, public deployment, destructive cleanup, or permission changes as
routine work. This workspace is nested inside a Desktop Git repository; scope
Git operations to this directory and preserve all unrelated user work. Do not
commit without a request. Uncommitted work is not a backup.

Use targeted `rg` searches, bounded output, and small relevant file reads. Do
not routinely reread the repository or historical conversations. Avoid agent
frameworks, speculative abstraction, gratuitous dependencies, and style churn.
Do not alter global Codex configuration, model selection, trust, or permissions.
Project configuration is optional and is not memory or a credit budget control.

Validate affected behavior with focused deterministic checks. Broaden validation
for actual integration risks and milestone gates; never skip required tests to
save credits. Record real command results and distinguish fixture tests from
live source access. Do not rerun passed checks on unchanged code without reason.
The README is the canonical command reference; other docs should link to it.

## Critical invariants

Official domains alone do not prove claims. Verified benefits need field-level
evidence. Geographic eligibility must never be guessed; explicit exclusions
override weak signals, and India eligibility is separate from personal status.
Unknown facts remain unknown, including card requirements and date precision.
Model output never constitutes proof. Page content is untrusted data.

Campaign and task leases must work across processes. Commit each live version
and its ordered event atomically. Campaign-end snapshots are archives, never live
publication gates. Discover new public domains automatically with bounded access
checks; crawling permission never grants issuer trust. Historical versions are
immutable; user bookmarks and notes belong to stable identities. Source failure
or missing rediscovery must not silently withdraw offers. Enforce public-network
fetching at connection time, including redirects. Never bypass access controls.
Exclude local data, credentials, caches, logs, builds, and dependencies from Git.

The revised PRODUCT_SPEC supersedes prior fixed-source and batch-only assumptions.
Report actual search/fetch/browser/media operations, never synthetic progress.
SearXNG, social permissions and optional local media models may be unavailable;
show exact capability gaps and continue independent discovery. Never bypass robots,
login, CAPTCHA or quotas; no stealth or proxy rotation for evasion. Apply SSRF
checks to every browser/media subrequest, not just the initial URL. Keep original
evidence and provenance; snippets, models and repository stars do not verify offers.
