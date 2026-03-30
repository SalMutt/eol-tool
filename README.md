# eol-tool — Hardware End-of-Life Checker

CLI tool and web dashboard for checking datacenter hardware end-of-life status. Queries manufacturer data sources for real EOL dates — no hardcoded or estimated dates.

## Features

- Checks 1000+ hardware models across 40+ manufacturers
- Real EOL dates from manufacturer sources (Intel ARK, Juniper EOL pages, Cisco bulletins, endoflife.date API)
- Playwright-based scrapers for JavaScript-rendered vendor pages
- Single-model lookup via REST API
- Bulk spreadsheet processing (xlsx input/output)
- Web dashboard with search, filters, collapsible manufacturer groups, and export
- SQLite cache with configurable TTL — refreshable with `eol-tool update`
- Risk categorization: security, support, procurement, informational
- Date source attribution: Manufacturer Confirmed, Community Database, Not Available
- Docker deployment with Chromium included

## Quick Start

### Docker Hub (easiest)

```bash
docker pull salmutt/eol-tool:latest
docker run -d -p 8080:8080 --name eol-tool salmutt/eol-tool:latest
```

Open http://localhost:8080

### Docker Compose (from source)

```bash
git clone https://github.com/SalMutt/eol-tool.git
cd eol-tool
docker compose up -d
```

Open http://localhost:8080

### Local

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[api]"
playwright install chromium
```

Start the web UI and API:

```bash
eol-tool serve --port 8080
```

Or run a batch check:

```bash
eol-tool check --input data/inventory.xlsx --output results.xlsx
```

## Web UI

Open http://localhost:8080 after starting the server.

- **Single Model Lookup** — search any model without uploading a file
- **Bulk Upload** — drag and drop an xlsx spreadsheet for batch analysis
- **Dashboard** — filterable, sortable results grouped by manufacturer
- **Export** — download filtered or full results as xlsx or csv

## API Endpoints

```
GET  /api/health              Health check
GET  /api/lookup?model=X      Single model lookup (manufacturer optional)
POST /api/check               Upload xlsx for batch processing
GET  /api/sources             List data sources and cache status
```

### Example

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

## CLI Commands

```bash
eol-tool check --input models.xlsx --output results.xlsx   # Batch EOL check
eol-tool serve --port 8080                                  # Start web UI + API
eol-tool update                                             # Refresh cached data from sources
eol-tool update --source juniper                            # Refresh specific source
eol-tool cache stats                                        # Show cache status
eol-tool cache clear                                        # Clear all cached data
```

## Data Sources

| Source | Type | Coverage | Dates |
|--------|------|----------|-------|
| Intel ARK | Playwright scraper | Intel CPUs | Manufacturer Confirmed |
| Juniper EOL pages | HTTP scraper | Juniper switches/firewalls | Manufacturer Confirmed |
| Cisco EOL bulletins | Playwright scraper | Cisco firewalls/APs | Manufacturer Confirmed |
| endoflife.date API | REST API | Intel, NVIDIA, others | Community Database |
| Tech generation rules | Local | DDR3/4/5, CPU generations | Classification only |
| Vendor pattern rules | Local | Samsung, Seagate, WD, Kingston, Micron | Classification only |

Vendors without formal EOL programs (Samsung, Seagate, WD, Kingston, Micron, SK Hynix, Toshiba) are classified by technology generation but show "Not Available" for dates — because no manufacturer date exists.

## Spreadsheet Format

Input xlsx requires these columns:

| Column | Required | Description |
|--------|----------|-------------|
| Model | Yes | Hardware model name or part number |
| Manufacturer | Yes | Vendor name |
| Category | Yes | Hardware type (cpu, switch, ssd, memory, etc) |

## Architecture

```
Web UI → FastAPI → Check Pipeline
                        ↓
              ┌─────────┼──────────┐
              ↓         ↓          ↓
         Playwright   endoflife.date  Static Rules
         Scrapers     API (httpx)    (no dates)
              ↓
       Headless Chromium
              ↓
  Intel ARK / Cisco / Juniper

All results cached in SQLite (7-30 day TTL)
```

Priority chain: Manual overrides → Vendor scrapers → endoflife.date API → Static rules → Tech generation. Dated results always beat dateless results.

## Development

```bash
pip install -e ".[dev]"
pytest -v
ruff check src/ tests/
```

## License

MIT
