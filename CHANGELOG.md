# Changelog

## v2.3.0 (2026-04-14)

### Added
- **13 new manufacturer checkers:** Adaptec, ADATA, A-Tech, Axiom, Corsair, EVGA, Hitachi, HPE, IBM, Mellanox, MSI, SanDisk, Zotac
- **Generation dates database:** ~700 product-line date patterns in `data/generation_dates.csv` covering CPUs, SSDs, HDDs, NICs, and GPUs
- **Ordering code decoding** for Intel, AMD, Samsung, Micron, and Kingston part numbers
- **DDR speed-bin date matching** from memory part numbers (DDR3/DDR4/DDR5)
- **Manufacturer auto-detection** from model strings when manufacturer column is missing
- **QuickBooks import** with automatic category/condition prefix stripping
- **Item string retry:** if normalized model yields no result, the original item string is retried
- **Lifecycle estimation:** approximate EOL from release dates using category-specific product lifecycles
- Expanded AMD, Arista, Broadcom, Dell, Intel, KIOXIA, Micron, Mushkin, NVIDIA, PNY, Samsung, Seagate, Solidigm, Supermicro, Transcend checkers with product-line generation rules
- ~200 manual overrides for white-label optics, passive components, and edge-case models

### Fixed
- Junk filter false positives on valid models with category prefixes
- Manufacturer auto-detection for models with `CATEGORY:CONDITION:` prefixes
- CLI snapshot writes `last_run.json` after check completes (not before)
- Post-processing contradiction correction for models with dates but wrong status

### Changed
- Classification pipeline expanded with three-tier date resolution: manufacturer-confirmed → community database → generation estimates
- Date source field now distinguishes `manufacturer_confirmed`, `community_database`, and `generation_estimate`
- Status derivation uses EOL dates to correct contradictory status values
- Manual overrides file expanded from ~30 to ~200 entries

### Stats
- 39 manufacturer-specific checkers (up from 25 in v2.2.0)
- 100% classification rate — zero unknowns on tested inventory
- ~700 generation date patterns
- 1,574 tests passing, ruff clean

## v2.2.0 (2026-04-08)

### Added
- Release date tracking: new `release_date` field populated from Intel ARK launch dates and other sources
- Google site-restricted search as primary Intel ARK strategy for finding product pages
- Intel ARK expanded to cover NICs and SSDs with relevance scoring
- Juniper component date propagation from parent chassis EOL notices
- Manual overrides for 28+ previously-unknown models (Transcend, optics, misc)
- Intel Xeon E-2xxx and Scalable 3rd/4th gen technology generation classification rules
- Scraper health dashboard improvements
- CLI `--log-level` and `-v` flags for scraper diagnostic output
- endoflife.date improved cycle matching with date supplementation
- Scheduler with retry/backoff for automated scraper runs
- Non-root Docker container
- Diff reporting with ntfy push notifications
- Input filters with `--show-filtered` flag
- Generic optics classifier for white-label SFP/QSFP modules

### Fixed
- Intel ARK relevance scoring: strip ® and ™ from candidate text before matching
- Intel ARK word-order-independent matching via bare model extraction (e.g., "Processor E5-2683 v4" now matches "E5-2683 v4 Processor")
- Transcend SSD225S manual override normalization mismatch (TRAN SSD225S)
- Intel ARK search term construction for E-2xxx ("E-2136" → "Intel Xeon E-2136 Processor")
- Intel ARK search term construction for E3/E5 ("E5-2683V4" → "Intel Xeon E5-2683 v4 Processor")
- Intel ARK search term construction for Scalable ("SILVER 4310" → "Intel Xeon Silver 4310 Processor")
- Google CAPTCHA detection with graceful fallthrough to next search strategy

### Changed
- Dell and Intel static dates relabeled from "approximate" to "community_database" for honest sourcing
- Date sources now use two confidence tiers: "manufacturer_confirmed" and "community_database"
- All scrapers use DRY shared pipeline (CLI and API use identical code paths)
- Security hardening: non-root Docker, input validation, rate limiting

### Stats
- 1,005 models across 42 manufacturers
- 99.9% classification rate (1 legitimate unknown: Dell M.2 with no model number)
- 84 Intel models with manufacturer-confirmed dates (up from 65 in v2.1.0)
- 115+ verified EOL dates total (81 manufacturer-confirmed, 34 community database)
- 1,175 tests passing, ruff clean

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
