# eol-tool

Hardware end-of-life lifecycle management for datacenter inventory.

eol-tool takes a hardware inventory spreadsheet, classifies every model by EOL status with dates, and covers 39 manufacturers with dedicated checkers. It queries manufacturer websites, scrapes real lifecycle data, decodes part numbers, and applies technology-generation dating to produce actionable EOL reports.

## Quick Start

### Docker (recommended)

```bash
docker compose up -d
```

Open http://localhost:8080, upload your inventory spreadsheet, and get results.

Or run the pre-built image directly:

```bash
docker run -d -p 8080:8080 --name eol-tool salmutt/eol-tool:latest
```

### CLI

```bash
pip install -e ".[api]"
playwright install chromium

eol-tool check --input inventory.xlsx --output results.xlsx
```

## Features

- **39 manufacturer-specific checkers** with real product-line logic, plus endoflife.date API fallback
- **Live scrapers** for Intel ARK, Juniper EOL pages, and Cisco EOL bulletins via Playwright
- **Ordering code decoding** for Intel, AMD, Samsung, Micron, SK Hynix, and Kingston part numbers
- **DDR speed-bin date matching** from memory part numbers (DDR3/DDR4/DDR5)
- **~700 generation date patterns** for approximate dating across CPU, SSD, HDD, NIC, and GPU product lines
- **QuickBooks and spreadsheet import** — handles category/condition-prefixed item strings natively
- **Manufacturer auto-detection** from model strings when manufacturer column is missing
- **100% classification rate** — zero unknowns on tested inventory
- **Web dashboard** with filtering, search, manufacturer grouping, and xlsx/csv export
- **1,574 automated tests** with ruff linting

## Supported Manufacturers

**Networking:** Arista, Broadcom, Cisco, Juniper, Mellanox

**Servers & Motherboards:** ASRock, ASUS, Chenbro, Dell, Gigabyte, HPE, IBM, MSI, Supermicro

**CPUs:** AMD, Intel

**GPUs:** EVGA, NVIDIA, PNY, Zotac

**Storage:** ADATA, Corsair, Hitachi, Kingston, KIOXIA, Micron, Mushkin, OCZ, Samsung, SanDisk, Seagate, Solidigm, Toshiba, Transcend, WD

**Memory:** A-Tech, Axiom (plus Kingston, Micron, Samsung for memory part number decoding)

**Controllers & Accessories:** Adaptec, Dynatron

**Generic:** White-label optics (SFP/QSFP/XFP modules)

Additional manufacturers are covered automatically via the [endoflife.date](https://endoflife.date) API.

## Input Formats

eol-tool accepts xlsx files in two formats:

### Standard template

| Column | Required | Example |
|--------|----------|---------|
| Model | Yes | EX4300-48T, EPYC 7413, PM893, R630 |
| Manufacturer | Yes | Juniper, AMD, Samsung, Dell |
| Category | Yes | switch, cpu, ssd, server, memory, nic, hdd |

Download a pre-formatted template from the web UI.

### QuickBooks export

eol-tool auto-detects QuickBooks-style exports where models appear as `CATEGORY:CONDITION:Model` in the Item column (e.g., `PROCESSORS:NEW:Intel Xeon E3-1230 v5`). Category and condition are extracted automatically.

**MPN preference:** When both a Model and MPN (Manufacturer Part Number) column exist, eol-tool prefers the MPN for classification since it contains the specific ordering code needed for accurate identification.

**Manufacturer auto-detection:** When the Manufacturer column is missing or blank, eol-tool infers the manufacturer from the model string using known product-line prefixes and naming patterns.

## How Classification Works

eol-tool runs each model through a multi-stage pipeline:

### Priority chain

1. **Manual overrides** — local CSV for site-specific corrections
2. **Playwright scrapers** — real dates from Intel ARK, Cisco bulletins
3. **HTTP scrapers** — real dates from Juniper EOL pages
4. **endoflife.date API** — community-maintained lifecycle data
5. **Vendor pattern rules** — classification by product line without dates
6. **Technology generation rules** — DDR3/4/5, CPU generation, SSD generation

Dated results always beat dateless results, regardless of priority level.

### Three-tier date resolution

1. **Manufacturer-confirmed dates** — scraped directly from vendor EOL pages
2. **Community database dates** — from endoflife.date with cycle matching
3. **Generation estimates** — approximate dates from `data/generation_dates.csv` patterns

### Post-processing

- **Status derivation:** EOL date in the past → `eol`, EOL date in the future → `eol_announced`, no EOL info → `active`
- **Contradiction correction:** if a model has a dated EOL but status says active, the status is corrected
- **Lifecycle estimation:** when only a release date exists, EOL is estimated using typical product lifecycles (5–10 years by category)
- **Item string retry:** if the normalized model yields no result, the original item string is tried as a fallback

## Output Columns

| Column | Description |
|--------|-------------|
| Model | Normalized model identifier |
| Manufacturer | Manufacturer name |
| Category | Hardware category (cpu, ssd, switch, etc.) |
| EOL Status | `active`, `eol`, `eol_announced`, or `unknown` |
| EOL Date | End-of-life date (when available) |
| EOS Date | End-of-support date (when available) |
| Release Date | Product launch/release date (when available) |
| Date Source | Where the date came from: `manufacturer_confirmed`, `community_database`, `generation_estimate`, or `none` |
| EOL Reason | Why the model is EOL: `manufacturer_declared`, `technology_generation`, `product_discontinued`, `vendor_acquired`, `community_data`, `manual_override` |
| Risk Category | `security`, `support`, `procurement`, or `informational` |
| Confidence | 0–100 score reflecting data source reliability |
| Source | Which checker produced the result |
| Notes | Human-readable explanation of the determination |

## Web Dashboard

The web UI at http://localhost:8080 provides:

- **Single model lookup** — type a model number and optional manufacturer for instant results
- **Bulk upload** — drag and drop an xlsx inventory file for batch processing
- **Template download** — blank xlsx with correct column headers and example rows
- Collapsible manufacturer groups with model counts
- Filter by EOL status, risk category, or manufacturer
- Search across all models
- Sort by name, count, EOL date, or risk level
- Export filtered or full results as xlsx or csv
- Date Source badges showing where each date came from

## REST API

```
GET  /api/health                          Health check
GET  /api/lookup?model=X&manufacturer=Y   Single model lookup
POST /api/check                           Bulk xlsx upload and processing
GET  /api/sources                         List data sources and cache status
```

**Example:**

```bash
curl "http://localhost:8080/api/lookup?model=EX4300-48T&manufacturer=Juniper"
```

```json
{
  "model": "EX4300-48T",
  "manufacturer": "Juniper",
  "status": "eol",
  "eol_date": "2023-03-31",
  "eos_date": "2026-03-31",
  "date_source": "manufacturer_confirmed",
  "risk_category": "security",
  "confidence": 90,
  "source": "juniper-eol"
}
```

## CLI

```
eol-tool check --input inventory.xlsx --output results.xlsx    Batch check
eol-tool serve --port 8080                                      Start web UI + API
eol-tool update                                                 Refresh all cached data
eol-tool update --source juniper                                Refresh one source
eol-tool cache stats                                            Show cache info
eol-tool cache clear                                            Clear all caches
eol-tool --version                                              Show version
```

## Risk Categories

| Risk | Hardware Types | Meaning |
|------|---------------|---------|
| **Security** | Switches, firewalls, routers | No security patches — active vulnerability risk |
| **Support** | Servers, CPUs, RAID controllers | No vendor support — failures have no repair path |
| **Procurement** | SSDs, HDDs, memory, drives | No replacement parts — procurement planning needed |
| **Informational** | Optics, coolers, cables, chassis | Low operational impact |

## Configuration

### Manual overrides

Add entries to `data/manual_overrides.csv` to override classification for specific models:

```csv
model,manufacturer,status,eol_reason,risk_category,eol_date,eos_date,source_url,notes,release_date,confidence
PM863,Samsung,eol,product_discontinued,procurement,,,,,2015-01-01,
```

Overrides take highest priority in the pipeline and are useful for site-specific corrections or models that automated checkers handle incorrectly.

### Generation dates

Add product-line date mappings to `data/generation_dates.csv`:

```csv
generation_pattern,release_date,eol_estimate,source
Haswell,2013-06-01,2019-12-31,intel-ark-historical
Broadwell,2015-06-01,2020-12-31,intel-ark-historical
```

The file contains ~700 patterns covering CPU generations, SSD product lines, HDD families, NIC generations, and GPU architectures. When a model matches a generation pattern, the release and estimated EOL dates are applied if no better source exists.

## Development

### Prerequisites

- Python 3.12+
- Node.js (for Playwright browser automation)

### Setup

```bash
git clone https://github.com/SalMutt/eol-tool.git
cd eol-tool
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
playwright install chromium
```

### Running tests

```bash
pytest
ruff check src/ tests/
```

### Adding a new manufacturer checker

1. Create `src/eol_tool/checkers/vendorname.py`
2. Extend `BaseChecker`, set `manufacturer_name` to the vendor name
3. Implement the async `check` method returning an `EOLResult`
4. If the vendor has a scrapable EOL page, use Playwright and set `date_source` to `manufacturer_confirmed`
5. If no EOL data source exists, use classification rules and set `date_source` to `none`
6. Register the checker in `src/eol_tool/registry.py`
7. Add tests in `tests/test_checkers/test_vendorname.py`
8. Run `pytest` and `ruff check src/ tests/`

## Docker

The included `Dockerfile` builds an image with Python 3.12, Chromium (for Playwright scrapers), and all dependencies.

```bash
# Build locally
docker build -t eol-tool .

# Or use docker compose
docker compose up -d
```

The `docker-compose.yml` mounts `./data` for manual overrides and generation dates, and uses a named volume for the SQLite cache.

**Environment variables:**

| Variable | Default | Description |
|----------|---------|-------------|
| `EOL_TOOL_CACHE_DIR` | `~/.cache/eol-tool` | SQLite cache directory |
| `EOL_TOOL_HOST` | `0.0.0.0` | API server bind address |
| `EOL_TOOL_PORT` | `8080` | API server port |
| `EOL_TOOL_LOG_LEVEL` | `INFO` | Log level (DEBUG, INFO, WARNING, ERROR) |

## Known Limitations

- **Intel ARK CAPTCHA:** Intel ARK blocks automated scraping from datacenter IPs. Run from a residential IP to populate the cache, then deploy the cached data.
- **Dell and Supermicro:** These vendors don't provide scrapable EOL data. Classification is based on product-line rules without dates.
- **Generation estimates:** Most dates (~91%) are generation estimates, not manufacturer-confirmed. The `date_source` column distinguishes these.
- **Lifecycle-estimated EOL dates:** When only a release date exists, EOL is estimated using typical product lifecycles (5–10 years depending on category). These are approximations.

## License

[Apache 2.0](LICENSE)

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup, adding new vendor checkers, and code style guidelines.
