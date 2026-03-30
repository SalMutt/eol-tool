# eol-tool

**Hardware End-of-Life Checker** — Real manufacturer EOL dates for datacenter hardware.

eol-tool checks your hardware inventory against live manufacturer data sources and returns real end-of-life dates, end-of-support dates, and risk classifications. No hardcoded dates, no guesswork — every date is sourced from the manufacturer or a verified community database.

## Quick Start

**Docker (recommended):**

```bash
docker run -d -p 8080:8080 --name eol-tool salmutt/eol-tool:latest
```

Open http://localhost:8080

**From source:**

```bash
git clone https://github.com/SalMutt/eol-tool.git
cd eol-tool
docker compose up -d
```

**Local development:**

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[api]"
playwright install chromium
eol-tool serve --port 8080
```

## How It Works

eol-tool queries manufacturer websites and APIs for real lifecycle data:

| Source | Method | What It Returns |
|--------|--------|----------------|
| **Intel ARK** | Playwright scraper | Marketing Status, Launch Date, End of Servicing Date |
| **Juniper EOL** | HTTP scraper | End of Life date, End of Support date per product family |
| **Cisco bulletins** | Playwright scraper | End of Sale, End of SW Maintenance, Last Date of Support |
| **endoflife.date** | REST API | Community-maintained lifecycle data for common products |

For vendors without public EOL programs (Samsung, Seagate, WD, Kingston, Micron, SK Hynix, Toshiba, Dell, Supermicro), eol-tool classifies hardware by technology generation and product line. These vendors show "Not Available" for dates because no manufacturer date exists — the tool is honest about this rather than guessing.

### Priority Chain

When multiple data sources have information about a model, eol-tool picks the best result:

1. **Manual overrides** — local CSV for site-specific corrections
2. **Playwright scrapers** — real dates from Intel ARK, Cisco bulletins
3. **HTTP scrapers** — real dates from Juniper EOL pages
4. **endoflife.date API** — community-maintained dates
5. **Vendor pattern rules** — classification without dates
6. **Tech generation rules** — DDR3/4/5, CPU generation, SSD generation

Dated results always beat dateless results, regardless of priority level.

## Web Dashboard

The web UI at http://localhost:8080 provides three workflows:

**Single Model Lookup** — Type a model number and optional manufacturer to get instant results. No file upload required.

**Bulk Upload** — Drag and drop an xlsx spreadsheet with your hardware inventory. If the spreadsheet contains raw inventory (Model, Manufacturer, Category columns), eol-tool processes it through all checkers and returns results. If it contains pre-processed results (with EOL Status already filled), it displays them directly.

**Template Download** — Download a blank xlsx template with the correct column headers and example rows.

### Dashboard Features

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

## Spreadsheet Format

eol-tool accepts xlsx files with these columns:

| Column | Required | Example |
|--------|----------|---------|
| Model | Yes | EX4300-48T, EPYC 7413, PM893, R630 |
| Manufacturer | Yes | Juniper, AMD, Samsung, Dell |
| Category | Yes | switch, cpu, ssd, server, memory, nic, hdd |

Download a pre-formatted template from the web UI.

## Risk Categories

eol-tool assigns risk levels to EOL hardware based on category:

| Risk | Hardware Types | Meaning |
|------|---------------|---------|
| **Security** | Switches, firewalls, routers | No security patches — active vulnerability risk |
| **Support** | Servers, CPUs, RAID controllers | No vendor support — failures have no repair path |
| **Procurement** | SSDs, HDDs, memory, drives | No replacement parts — procurement planning needed |
| **Informational** | Optics, coolers, cables | Low operational impact |

## Architecture

```
                    +------------------+
                    |     Web UI       |
                    |  (React + XLSX)  |
                    +--------+---------+
                             |
                    +--------v---------+
                    |    FastAPI        |
                    |  /api/lookup      |
                    |  /api/check       |
                    +--------+---------+
                             |
                    +--------v---------+
                    |  Check Pipeline   |
                    |  select_best()    |
                    +--------+---------+
                             |
           +-----------------+------------------+
           |                 |                  |
  +--------v-------+ +------v-------+ +--------v--------+
  |   Playwright    | |    httpx     | |  Static Rules    |
  |   Scrapers      | |   Scrapers   | |  (no dates)      |
  |                 | |              | |                   |
  |  Intel ARK      | |  Juniper     | |  25+ vendor       |
  |  Cisco EOL      | |  endoflife   | |  checkers         |
  +--------+-------+ +------+-------+ +------------------+
           |                 |
  +--------v-----------------v-------+
  |         SQLite Cache              |
  |    7-30 day TTL per source        |
  +----------------------------------+
```

## Supported Manufacturers

AMD, Arista, ASRock, ASUS, Broadcom, Brocade, Chenbro, Cisco, Corsair, Dell, Dynatron, EVGA, Gigabyte, HPE, Hitachi, IBM, Intel, Juniper, KIOXIA, Kingston, Mellanox, Micron, MSI, Mushkin, NVIDIA, OCZ, PNY, Samsung, SanDisk, Seagate, SK Hynix, Solidigm, Supermicro, Toshiba, Transcend, WD, Zotac

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup, adding new vendor checkers, and code style guidelines.

## License

[Apache 2.0](LICENSE)
