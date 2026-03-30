# Changelog

## v2.0.0 (2025-03-30)

### Features

- Real EOL dates from manufacturer sources (Intel ARK, Juniper, Cisco, endoflife.date)
- Playwright-based scrapers for JavaScript-rendered vendor pages
- FastAPI REST API with single-model lookup and bulk processing
- Web dashboard with search, filters, collapsible groups, and export
- Template download for new users
- Raw inventory upload with live processing
- Docker deployment with Chromium included
- 25+ vendor checkers covering 40+ manufacturers
- Priority-based check pipeline — dated results beat dateless
- SQLite cache with configurable TTL
- eol-tool update command for cache refresh

### Data Sources

- Intel ARK (Playwright scraper) — manufacturer confirmed dates
- Juniper EOL pages (HTTP scraper) — manufacturer confirmed dates
- Cisco EOL bulletins (Playwright scraper) — manufacturer confirmed dates
- endoflife.date API — community database dates
- Technology generation rules — classification without dates
- Vendor pattern matching — classification without dates
