# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [2.1.0] - 2026-04-03

### Added
- Input filter: strips junk inventory rows (server build configs, internal codes, capacity descriptions, vague labels) before classification. Filtered rows preserved on separate "Filtered" sheet in output xlsx. CLI --show-filtered flag to display filtered rows.
- Generic optics classifier: automatically classifies white-label SFP/QSFP/XFP/CFP transceivers as active commodity items. Handles DWDM channel optics and converter modules.
- Technology generation rules for 11 new manufacturers: ASUS server platforms, IBM RAID controllers and switches, NVIDIA professional GPUs, Hitachi legacy drives, Corsair DDR5, Kingston unusual parts, Adaptec RAID, ASRock server boards, PNY GPUs, Zotac GPUs, HPE legacy drives.
- Manual overrides management: CRUD API endpoints (GET/POST/PUT/DELETE /api/overrides) with CSV import/export. Frontend management page with add/edit/delete forms, search, sorting, and validation.
- Diff reporting: compare two result sets and surface status changes, new EOL dates, and risk escalations. CLI command (eol-tool diff) and --diff flag on check command. Compact text format for notifications, JSON format for programmatic use. Exit code 1 on critical changes.
- Scheduled checks with ntfy: periodic re-check daemon with diff-based notifications. Configurable severity filtering (critical/warning/all/none). Priority mapping to ntfy levels. Error notifications on check failures. Docker-compose scheduler service. CLI commands: eol-tool schedule and eol-tool notify.
- Retry with unknowns: --retry-unknowns flag re-checks only UNKNOWN/NOT_FOUND models from a previous results file, merging with already-classified results. Saves time when iterating on the last few unclassified models.
- Rate limit resilience: exponential backoff with jitter for all HTTP-based checkers. Configurable retry count and delays. Smart retry filtering (retries 429/5xx/timeout, skips 404/400). Per-run retry summary in CLI output.
- Scraper health dashboard: in-memory per-checker metrics tracking (success rate, response times, retries, last error). API endpoint GET /api/health with actionable recommendations. Frontend System Health page with status cards, success rate bars, and auto-refresh.
- API status endpoint: GET /api/status returns last check time, model counts, cache stats, and scheduler status.
- Cache freshness indicators in frontend: relative timestamps with color-coded staleness (green/yellow/red) at dashboard, manufacturer group, and model levels.
- Manual overrides count in dashboard summary statistics.
- Environment variable configuration: EOL_TOOL_DATA_DIR, EOL_TOOL_NTFY_TOPIC, EOL_TOOL_NTFY_TOKEN, EOL_TOOL_NTFY_URL, EOL_TOOL_SCHEDULE_INTERVAL, EOL_TOOL_RESULTS_DIR, EOL_TOOL_RETRY_MAX, EOL_TOOL_RETRY_BASE_DELAY.
- Docker scheduler service in docker-compose.yml for automated periodic checks.

### Fixed
- Docker overrides path resolution: shared paths.py module with EOL_TOOL_DATA_DIR env var fallback. Manual overrides imported via web UI now persist to host filesystem.
- React overrides page crash: moved early return statement after all hook declarations to fix "Rendered fewer hooks than expected" error.
- DWDM optics (C30 SFPP-10G-DW30, etc.) incorrectly filtered as junk: added SFPP recognition to input filter optics patterns.
- 8 pre-existing TestRealCSV test failures fixed to match current manual_overrides.csv contents.
- Verbose CLI warnings (no-manufacturer rows, Cisco no-bulletin messages) suppressed to debug level with --verbose flag.

### Changed
- Classification rate improved from 94% (967/1028) to 97% (970/973 real hardware) with 23 junk rows filtered and 3 remaining unknowns (data quality issues in source).
- Manual overrides CSV matching uses normalized model strings for reliable pattern matching.
- Test suite expanded from 856 to 1174+ tests. Coverage improved from 84% to 85%.

## [2.0.0] - 2025-03-30

### Added
- Real EOL dates from manufacturer sources (Intel ARK, Juniper, Cisco, endoflife.date).
- Playwright-based scrapers for JavaScript-rendered vendor pages.
- FastAPI REST API with single-model lookup and bulk processing.
- Web dashboard with search, filters, collapsible groups, and export.
- Template download for new users.
- Raw inventory upload with live processing.
- Docker deployment with Chromium included.
- 25+ vendor checkers covering 40+ manufacturers.
- Priority-based check pipeline — dated results beat dateless.
- SQLite cache with configurable TTL.
- eol-tool update command for cache refresh.

### Data Sources
- Intel ARK (Playwright scraper) — manufacturer confirmed dates.
- Juniper EOL pages (HTTP scraper) — manufacturer confirmed dates.
- Cisco EOL bulletins (Playwright scraper) — manufacturer confirmed dates.
- endoflife.date API — community database dates.
- Technology generation rules — classification without dates.
- Vendor pattern matching — classification without dates.
