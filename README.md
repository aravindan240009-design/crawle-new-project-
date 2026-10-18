# Dynamic Opportunity Radar

A local opportunity dashboard for Chennai/India and worldwide exploration. Search
new sources across food, travel, local services, shopping, events, learning, jobs,
AI, cloud, developer tools and open source. Provisional results appear immediately,
then receive evidence as pages are checked. No mandatory login, paid API or model.

The backend serves the production React dashboard at **http://127.0.0.1:8765**.
Your PC must be running, awake and online to collect sources. Scheduling is
initially **continuous, disarmed** on a new database. Existing preferences are
preserved. Daily mode defaults to 08:00 Asia/Kolkata when selected.
Manual scans work without enabling scheduling.

## Install and start — Windows

Requirements: Python 3.11+ and Node 22.12+ (tested Python 3.11.9, Node 24.15.0).
Run PowerShell from `C:\Users\ashok\OneDrive\Desktop\crawleee`:

```powershell
.\scripts\setup.ps1
.\scripts\start.ps1
```

If script execution is restricted by your organization, do not change its policy;
run the underlying commands directly:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --use-feature=truststore -r requirements.lock
$env:NODE_USE_SYSTEM_CA = '1'
Set-Location frontend
npm.cmd ci
npm.cmd run build
Set-Location ..
.\.venv\Scripts\python.exe -m backend serve
```

`scripts/start.cmd` is another launch option. Keep the terminal open; Ctrl+C stops
the server gracefully. Normal use requires no frontend development server.
Nothing installs a startup task or changes power/sleep settings automatically.
The development session left a hidden local server running; `scripts/stop.ps1`
validates its recorded launcher PID before stopping that workspace's process.
Then use the normal foreground start script when desired.

## Linux / macOS

From the repository root with Python 3.11+ and supported Node installed:

```sh
sh scripts/setup.sh
sh scripts/start.sh
```

Use `.venv/bin/python` in place of the Windows interpreter in commands below.
The application code is portable; OS-specific launch instructions outside Windows
have not been executed in this development environment.

## Use it

1. Open **Live discovery**, choose budgets/categories, and **Start discovery**.
   Unknown domains enter the queue automatically. Provisional results appear before
   fetching; evidence updates publish individually. Seeds are optional starting points.
2. Browse Discover or News. Search, filters and sorting query local results;
   they never trigger a crawl. Save views or export the exact filtered set.
3. Open **View evidence** for excerpts, terms, restrictions, unknowns, provenance
   and changes. Bookmark, dismiss or write notes independently of content versions.
4. Activity shows real persisted events, including original timestamps on replay.
   Pause/resume/cancel preserve committed results. Frontier, Coverage, Media and
   Capabilities show actual work and missing runtimes. Public lead submissions queue
   for a discovery campaign; permitted fetching does not establish issuer identity.
5. In Settings, explicitly enable daily or continuous scheduling. Continuous mode
   discovers new sources and revisits due frontier pages. Missed intervals coalesce
   to one catch-up while the worker is available. Manual/API/CLI triggers share a
   database lease. Use Scan activity for errors, retries and historical snapshots.
6. Create local **Alert rules** in Live discovery. Configure IST quiet hours in
   Settings. Provisional alerts require explicit opt-in; confidence and cooldowns apply.
7. Explicit source tests and legacy seed scans remain available through Sources,
   API and CLI. They cannot overlap an active discovery campaign.

### Local search service

Broad web discovery uses local SearXNG. GitHub and queued public pages can run when
search is unavailable. Start Docker Desktop, then run on Windows:

```powershell
.\scripts\setup-search.ps1
```

This mirrors existing Windows trusted root certificates into an ignored,
container-only directory while keeping TLS verification enabled. A pinned SearXNG
image binds only to **127.0.0.1:8088**, with JSON search enabled and a 768 MB memory
cap. Engine errors/rate limits are reported; search coverage is not guaranteed.

On Linux/WSL with Docker running:

```sh
mkdir -p data/host-ca
export SEARXNG_SECRET=$(python3 -c 'import secrets; print(secrets.token_hex(32))')
docker compose up -d
```

Use established system CA provisioning if needed; never disable TLS checks.
For a small real search health check:

```powershell
Invoke-RestMethod 'http://127.0.0.1:8088/search?q=Chennai+free+workshop&format=json'
```

Stop only this sidecar with `docker stop crawleee-searxng-1`. Existing results remain.

### Optional browser and media

Crawlee dispatches bounded batches through the safe HTTP fetcher. To install the
optional browser runtime, then enable rendering in campaign controls:

```powershell
.\.venv\Scripts\python.exe -m playwright install chromium
```

Every browser HTTP subrequest goes through the same pinned transport; direct
network fallback is blocked. No personal cookies or anti-bot evasion are used.
Memory pressure reduces concurrency and defers browser/media work.

Relevant direct captions/images/audio/MP4 files enter Media. Files are capped at
2 MB; streaming manifests and unrestricted downloaders are disabled. Temporary
files are removed after processing. Caption timestamps are preserved; OCR/ASR
remains machine-extracted evidence, never issuer verification.

OCR requires a separately installed Tesseract executable with English `eng` and
Tamil `tam` language data. Check with `tesseract --list-langs`. Optional ASR setup:

```powershell
.\.venv\Scripts\python.exe -m pip install --use-feature=truststore faster-whisper
$env:RADAR_WHISPER_MODEL_DIR = 'C:\path\to\already-downloaded-multilingual-model'
```

Review the selected model's license/size before obtaining it separately. Tamil
requires a multilingual model, not an English-only `.en` model. The app uses local
files only and never downloads models. ffmpeg must be installed for audio conversion;
it reads local files with a 120-second input limit. Extraction uses a bounded process.
Live Tamil/English OCR/ASR accuracy is **not validated** on this PC: optional models
are absent. Capabilities shows exact missing dependencies. Instagram/global reels
discovery is not available; see [capabilities](docs/SOURCE_CAPABILITIES.md).

**Interpretation:** Partially verified means a specific official claim was found,
but material conditions are incomplete. India eligible needs explicit geographic
evidence; it does not prove personal student/startup eligibility. Unknown deadlines,
delivery availability, fees and card requirements stay unknown. Scores rank results;
they are not probabilities. Advertised credits are not guaranteed awards.

### Tracker, reminders and digest

Open an opportunity detail and use **Application tracker** to record Interested,
Preparing, Applied, Accepted, Declined or Archived. Set an optional personal
reminder date in IST. Status and reminders survive new versions and restarts;
they do not change official eligibility, claims or deadlines. Due reminders create
deduplicated in-dashboard alerts while the local server is running. Accepted,
declined and archived items no longer create reminders.

**Tracker** shows your applications and exports an `.ics` calendar containing
personal reminder dates as all-day events and only precisely known official
deadlines as timed UTC events. Import the file into your calendar yourself; there
is no account connection or automatic calendar write.

**Digest** summarizes the last 7, 14 or 30 days of completed discoveries and
material changes, plus precise deadlines in the next seven days and your personal
reminders. It excludes dismissed items, confirmed geographic exclusions and news
from discovery sections. Changes come from immutable publication history even
when alert creation is disabled. Export as Markdown; nothing is emailed or sent.

## Scan, build and test

All commands below start in the repository root unless a directory change is shown.

```powershell
# Full headless live scan, or selected sources; these perform real network requests.
.\.venv\Scripts\python.exe -m backend scan
.\.venv\Scripts\python.exe -m backend scan --source cloudflare-workers --source ollama-releases
.\.venv\Scripts\python.exe -m backend scan --incremental

# Deterministic backend acceptance tests; no public network needed.
.\.venv\Scripts\python.exe -m pytest -q

# Isolated 10,000-row query benchmark.
.\.venv\Scripts\python.exe -m scripts.benchmark

Set-Location frontend
npm.cmd test
npm.cmd run build
$env:NODE_USE_SYSTEM_CA = '1'
npx.cmd playwright install chromium
npm.cmd run test:e2e
Set-Location ..
```

CLI exit codes: 0 completed, 2 completed with source errors, 1 failed/canceled,
3 another scan already owns the lease. A due-source cycle with no due sources is
explicitly skipped; it does not publish an empty replacement or generate failure alerts.
PowerShell may display a native nonzero exit as an error; inspect the JSON status.

For an interactive **isolated demo**, use a separate terminal:

```powershell
$env:RADAR_FIXTURES = '1'
$env:RADAR_PORT = '8766'
.\.venv\Scripts\python.exe -m backend serve
# Open http://127.0.0.1:8766; demo.sqlite is separate from radar.sqlite.
```

Close that terminal to discard its environment variables. Fixtures are labeled
DEMO and cannot enter the real database through normal operation. Browser tests
use their own timestamped data directory under ignored `data/`.

## Configuration and source extension

Seed configuration is `sources/registry.yaml`; the frontend edits the persisted
SQLite configuration. Changing seed YAML does not silently overwrite UI edits.
Explicit synchronization:

```powershell
.\.venv\Scripts\python.exe -m backend export-sources data\sources.yaml
# Edit data\sources.yaml, then explicitly import its entries:
.\.venv\Scripts\python.exe -m backend import-sources data\sources.yaml
```

Import validates every entry before a transaction; importing existing IDs replaces
their configuration. Add an HTML page, RSS/Atom feed, public GitHub releases endpoint,
community feed or supported public HN search through Sources. An empty official-domain
list means untrusted. Do not approve a hosting platform globally for an arbitrary
publisher. Review ownership and source terms; the adapter still enforces robots.txt,
public network addresses, quotas and content budgets. See
[source policy](docs/SOURCE_POLICY.md) and [architecture](docs/ARCHITECTURE.md).

New parser types belong in `backend/extract.py:collect` with a strict `Source.adapter`
choice, fixture tests and documented access policy. They must use `Fetcher`, never
an unrestricted HTTP client. Domain approval is not evidence of an offer.

Optional environment variables: `RADAR_DATA_DIR` (database directory), `RADAR_PORT`
(default 8765), `RADAR_FIXTURES=1` (demo mode). `.env.example` is documentation;
environment files are not implicitly loaded. The app binds to 127.0.0.1 only.

## Optional automatic startup

Windows: explicitly run `scripts/install-startup.ps1` to register a per-user logon
task named **Global Opportunity Radar**. Review it first. The task starts the server;
the application owns scheduling, preventing duplicate OS/application schedules.
It does not wake or keep awake the PC. To uninstall:

```powershell
Unregister-ScheduledTask -TaskName 'Global Opportunity Radar' -Confirm:$true
```

Linux: copy `scripts/radar.service.example` to
`~/.config/systemd/user/radar.service`, replace both `path/to/crawleee` paths, then
explicitly run `systemctl --user daemon-reload` and
`systemctl --user enable --now radar`. Undo with
`systemctl --user disable --now radar`. This starts with the user session; it does
not configure lingering. Do not add cron scans alongside the application scheduler.

macOS: run `sh scripts/start.sh` in Terminal, or explicitly configure a user LaunchAgent
whose ProgramArguments are the absolute `.venv/bin/python`, `-m`, `backend`, `serve`,
and whose WorkingDirectory is this repository. Use `launchctl bootstrap gui/$(id -u)`
with your reviewed plist; undo with `launchctl bootout`. No plist is auto-installed.

## Backup, restore, retention and deletion

For an online consistent SQLite backup (uses the SQLite backup API, including WAL):

```powershell
.\.venv\Scripts\python.exe -m backend backup data\radar-backup.sqlite
.\.venv\Scripts\python.exe -m backend restore data\radar-backup.sqlite --into data\restored
$env:RADAR_DATA_DIR = (Resolve-Path data\restored).Path
.\.venv\Scripts\python.exe -m backend serve
```

Backup refuses an existing target. Restore verifies integrity, writes only a new
database and disarms automatic scans; it never overwrites live data. Backups may
contain your notes, so store them privately. Copying an open `.sqlite` alone is not
a consistent backup. This workspace is in OneDrive: an actively synced SQLite file
is not a backup; for everyday use, consider `RADAR_DATA_DIR` in a nonsynced local
folder. Application data is Git-ignored, but that does not control OneDrive.

Settings → **Apply retention now** removes expired raw responses and terminal
campaign activity using separate configured ages. Active/interrupted events,
immutable published evidence and saved state remain. Replay reports retention gaps.
To deliberately
delete all collected data and personal state while retaining source configuration,
stop all Radar processes, wait 40 seconds, back up if desired, then explicitly run:

```powershell
.\.venv\Scripts\python.exe -m backend delete-local-data --confirm DELETE-LOCAL-DATA
```

This is not secure disk erasure and does not delete separate backups or screenshots.
CSV/JSON export is available in the dashboard with the same filtering predicates.

## Optional local model

Install/manage Ollama and a model yourself if desired; no automatic model download.
Enable the existing model name in Settings. Only `http://127.0.0.1:11434` is supported
as a separately trusted local integration. Requests are serialized, cached, limited
to 2K context/80 output tokens, and time out after 15 seconds. Output must select all
supplied fact/condition sentences; unsupported content falls back to deterministic
summaries. This deliberately conservative integration does not invent paraphrases
or verify claims. Normal operation is tested with no model.

## Troubleshooting and maintenance

- **Offline/failed sources:** inspect Sources and Scan activity. A failed source
  never proves an offer ended. All-source failure retains the previous snapshot.
  Robots denial, oversized content, unsupported encodings and JavaScript-only pages
  are explicit errors. Do not bypass logins, CAPTCHAs or access policies.
- **Interrupted scan:** after the 90-second lease expires, the next status/startup
  reconciles it as interrupted. Discovery campaigns resume the remaining frontier
  with a new worker generation; old workers cannot publish. In-flight requests
  restart rather than resuming bytes. Legacy source scans retry as a fresh roster.
- **Port in use:** stop the other Radar instance, or choose `RADAR_PORT` before
  launching. Do not expose the server publicly. Browser tests require port 8766.
- **TLS installation failure:** the setup scripts use the OS certificate store
  for pip/Node. No TLS verification is disabled. Corporate trust configuration
  belongs to the device administrator.
- **403 mutation:** reload the dashboard to get a fresh local-session token.
  Host and Origin checks reject cross-site access. API docs are at `/api/docs`;
  mutation clients need `/api/session` and `X-Radar-Token`.
- **No exact date matches:** date-only/unknown-timezone deadlines deliberately do
  not pass 24-hour/3/7/30-day filters. They remain inspectable in details.
- **Update dependencies:** inspect official release compatibility, update the
  virtual environment/npm manifests, regenerate `requirements.lock` with
  `.\.venv\Scripts\python.exe -m pip freeze`, preserve `frontend/package-lock.json`,
  run affected tests/build and regenerate license reports. Do not casually change
  locked versions. The Starlette test client currently emits a non-failing httpx
  deprecation warning; production requests use httpcore.

See [testing](docs/TESTING.md), [measured benchmarks](docs/BENCHMARKS.md),
[current progress](docs/PROGRESS.md), and [product specification](docs/PRODUCT_SPEC.md).
The project does not promise exhaustive web/social coverage, perfect extraction,
or guaranteed scan duration. Unsupported shopping/event facts remain unknown;
provider-specific extraction improvements remain useful follow-up work.

## License and privacy

New code is MIT-licensed. Dependency versions and licenses are in
[Python licenses](docs/PYTHON_LICENSES.md) and
[frontend licenses](docs/FRONTEND_LICENSES.md). No analytics, telemetry exporter,
external fonts or paid application integrations are configured. Direct source
fetches expose normal request metadata to those sources. Development-tool charges
are separate from the application's free components.

## Headless dynamic discovery

```powershell
.\.venv\Scripts\python.exe -m backend discover --queries 4 --pages 10 --seconds 180
```

CLI/API/scheduler share campaign locks. Archived snapshots do not gate live results.
A failed fetch marks prior evidence stale without withdrawing the offer.

Continuation: ?Continue under AGENTS.md. Read docs/PROGRESS.md and the active PLAN
task; inspect relevant workspace changes, implement the next ready task using only
needed context, run affected checks, and update the checkpoint. Do not restart
bootstrap or claim untested capabilities.?
