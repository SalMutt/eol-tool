# eol-tool

Hardware end-of-life checker for datacenter inventory.

[![CI](https://github.com/SalMutt/eol-tool/actions/workflows/ci.yml/badge.svg)](https://github.com/SalMutt/eol-tool/actions/workflows/ci.yml)
[![Docker Hub](https://img.shields.io/docker/v/salmutt/eol-tool?label=Docker%20Hub)](https://hub.docker.com/r/salmutt/eol-tool)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)](https://www.python.org/)
[![License: Apache 2.0](https://img.shields.io/badge/license-Apache%202.0-green)](LICENSE)

## What It Does

Checks datacenter hardware against manufacturer EOL databases. Queries Intel ARK, Juniper EOL pages, Cisco bulletins, endoflife.date API, and local rules engines. Supports 1000+ models across 40+ manufacturers with 97% classification rate.

## Quick Start

**Single model lookup:**

```bash
curl "http://localhost:8080/api/lookup?model=EX4300-48T&manufacturer=Juniper"
```

**Bulk check from spreadsheet:**

```bash
eol-tool check --input inventory.xlsx --output results.xlsx
```

**Docker:**

```bash
docker run -v ./data:/app/data salmutt/eol-tool:latest \
  eol-tool check --input /app/data/inventory.xlsx --output /app/data/results.xlsx
```

**Web dashboard:**

```bash
docker compose up -d
# Open http://localhost:8080
```

## Features

- **Bulk classification** from xlsx/csv input
- **Single model lookup** via API
- **Web dashboard** with search, filters, export
- **Diff reporting** — compare runs, surface changes
- **Scheduled checks** with ntfy notifications
- **Manual overrides** via web UI or CSV
- **Scraper health monitoring** dashboard
- **Input filtering** for junk/non-hardware rows
- **Rate limit resilience** with exponential backoff
- **Docker deployment** with persistent data

## Installation

**From source:**

```bash
git clone https://github.com/SalMutt/eol-tool.git
cd eol-tool
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev,api]"
playwright install chromium   # required for Intel ARK and Cisco scrapers
```

**Docker:**

```bash
docker pull salmutt/eol-tool:latest
```

Or with the full stack (web + scheduler):

```bash
docker compose up -d
```

## CLI Reference

### `eol-tool check` — bulk classification

```
eol-tool check --input inventory.xlsx --output results.xlsx [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `--input` | Path to input xlsx/csv spreadsheet |
| `--output` | Output file path |
| `--manufacturer` | Filter to a specific manufacturer (default: `all`) |
| `--concurrency` | Max concurrent requests (default: `5`) |
| `--no-cache` | Skip the result cache |
| `--show-filtered` | Display rows removed by the input filter |
| `--diff` | Previous results xlsx to diff against after checking |
| `--retry-unknowns` | Re-check only UNKNOWN/NOT_FOUND models from a previous results file |
| `--dry-run` | Load models and show summary without checking |
| `--skip-fallback` | Skip the endoflife.date fallback checker |

### `eol-tool diff` — compare two result files

```
eol-tool diff --previous old-results.xlsx --current new-results.xlsx [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `--previous` | Path to previous results xlsx |
| `--current` | Path to current results xlsx |
| `--format` | Output format: `text` or `json` (default: `text`) |
| `--verbose` | Show full details in text format |
| `--output` | Write diff to a file instead of stdout |

Exits with code 1 if critical changes are detected.

### `eol-tool schedule` — scheduled checks with notifications

```
eol-tool schedule --input inventory.xlsx --topic my-eol-checks [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `--input` | Input xlsx file |
| `--topic` | ntfy topic name (required) |
| `--interval` | Check interval in hours (default: `24`) |
| `--ntfy-url` | ntfy server URL (default: `https://ntfy.sh`) |
| `--ntfy-token` | ntfy auth token (also reads `EOL_TOOL_NTFY_TOKEN`) |
| `--notify-on` | When to notify: `critical`, `warning`, `all`, `none` (default: `warning`) |
| `--results-dir` | Directory for timestamped results |
| `--keep-results` | Number of result files to keep (default: `10`) |
| `--run-once` | Run a single check and exit |
| `--dry-run` | Run check but don't send notifications |

### `eol-tool notify` — send test notification

```
eol-tool notify --topic my-topic --message "Test notification"
```

| Option | Description |
|--------|-------------|
| `--topic` | ntfy topic name |
| `--message` | Message to send |
| `--ntfy-url` | ntfy server URL (default: `https://ntfy.sh`) |
| `--ntfy-token` | ntfy auth token |
| `--priority` | Notification priority 1-5 (default: `3`) |

### `eol-tool serve` — start the web server

```
eol-tool serve --port 8080
```

| Option | Description |
|--------|-------------|
| `--host` | Bind address (default: `0.0.0.0`) |
| `--port` | Port to listen on (default: `8080`) |

### `eol-tool cache stats` / `eol-tool cache clear`

```bash
eol-tool cache stats              # show cache statistics
eol-tool cache clear              # clear all cached results
eol-tool cache clear --manufacturer Intel   # clear one manufacturer
```

### `eol-tool list-checkers`

```bash
eol-tool list-checkers            # show registered EOL checkers
```

### `eol-tool update`

```bash
eol-tool update                   # refresh all cached source data
eol-tool update --source juniper  # refresh one source
```

### Single model lookup

There is no CLI `lookup` command. Use the API endpoint instead:

```bash
curl "http://localhost:8080/api/lookup?model=EX4300-48T&manufacturer=Juniper"
```

## API Reference

All endpoints are served from the `eol-tool serve` web server. Full OpenAPI docs available at `/docs` when the server is running.

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/` | Web dashboard |
| `GET` | `/api/lookup?model=X&manufacturer=Y` | Single model lookup |
| `POST` | `/api/check` | Bulk check (multipart xlsx upload) |
| `GET` | `/api/overrides` | List manual overrides |
| `POST` | `/api/overrides` | Create a manual override |
| `PUT` | `/api/overrides` | Update a manual override |
| `DELETE` | `/api/overrides?model=X&manufacturer=Y` | Delete a manual override |
| `GET` | `/api/overrides/export` | Export overrides as CSV |
| `POST` | `/api/overrides/import` | Import overrides from CSV |
| `POST` | `/api/diff` | Compare two result xlsx files |
| `GET` | `/api/health` | Scraper health metrics |
| `GET` | `/api/status` | System status (last check, counts, cache, scheduler) |
| `GET` | `/api/sources` | Data sources and cache freshness |

## Checker Priority Chain

When multiple data sources have information about a model, eol-tool picks the best result in this order:

1. **Vendor-specific scrapers** — Intel ARK, Juniper, Cisco, Supermicro, Dell
2. **Generic optics classifier** — white-label SFP/QSFP/XFP/CFP transceivers
3. **Technology generation rules** — DDR3/4/5, CPU generation, SSD generation (local, no HTTP)
4. **endoflife.date API** — community-maintained database
5. **Manual overrides** — user-defined CSV

Higher-priority checkers override lower ones. First definitive result wins. Dated results always beat dateless results, regardless of priority level.

## Risk Categories

| Risk | Hardware Types | Meaning |
|------|---------------|---------|
| **Security** | Switches, firewalls, routers | No firmware/security patches — active vulnerability risk |
| **Support** | Servers, CPUs, RAID controllers | No vendor warranty or RMA path |
| **Procurement** | SSDs, HDDs, memory, drives | Can't buy replacements — procurement planning needed |
| **Informational** | Optics, coolers, cables | Technically EOL but functionally fine, low operational impact |

## Scheduled Checks and Notifications

eol-tool can run periodic checks and send diff-based notifications via [ntfy](https://ntfy.sh).

**CLI:**

```bash
eol-tool schedule --input inventory.xlsx --topic my-eol-checks
```

**Docker:** The `eol-tool-scheduler` service in `docker-compose.yml` handles this automatically. Configure via environment variables.

**Environment variables:**

| Variable | Description |
|----------|-------------|
| `EOL_TOOL_NTFY_TOPIC` | ntfy topic name |
| `EOL_TOOL_NTFY_URL` | ntfy server URL (default: `https://ntfy.sh`) |
| `EOL_TOOL_NTFY_TOKEN` | ntfy auth token for private topics |
| `EOL_TOOL_SCHEDULE_INTERVAL` | Check interval in hours (default: `24`) |

**Notification severity levels:**

- `critical` — only notify on status changes to EOL or risk escalations
- `warning` — notify on critical changes plus new unknowns (default)
- `all` — notify on any change
- `none` — run checks silently

## Docker Deployment

Full deployment with web dashboard and scheduled checks:

```yaml
services:
  eol-tool:
    image: salmutt/eol-tool:latest
    ports:
      - "8080:8080"
    volumes:
      - ./data:/app/data
      - eol-cache:/root/.cache/eol-tool
    restart: unless-stopped
    environment:
      - EOL_TOOL_CACHE_DIR=/root/.cache/eol-tool
      - EOL_TOOL_DATA_DIR=/app/data

  eol-tool-scheduler:
    image: salmutt/eol-tool:latest
    volumes:
      - ./data:/app/data
      - ./results:/app/results
      - eol-cache:/root/.cache/eol-tool
    restart: unless-stopped
    environment:
      - EOL_TOOL_DATA_DIR=/app/data
      - EOL_TOOL_CACHE_DIR=/root/.cache/eol-tool
      - EOL_TOOL_RESULTS_DIR=/app/results
      - EOL_TOOL_NTFY_TOPIC=eol-checks
      - EOL_TOOL_SCHEDULE_INTERVAL=24
    command: >
      eol-tool schedule
        --input /app/data/eol_models_cleaned.xlsx
        --results-dir /app/results

volumes:
  eol-cache:
```

**Volume mounts:**

| Mount | Purpose |
|-------|---------|
| `./data:/app/data` | Input spreadsheets, manual overrides CSV |
| `./results:/app/results` | Timestamped result files from scheduled checks |
| `eol-cache` | Named volume for SQLite cache (shared between services) |

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `EOL_TOOL_DATA_DIR` | `./data` | Directory for input files and manual overrides |
| `EOL_TOOL_CACHE_DIR` | `~/.cache/eol-tool` | SQLite cache directory |
| `EOL_TOOL_RESULTS_DIR` | `./results` | Directory for scheduled check results |
| `EOL_TOOL_NTFY_URL` | `https://ntfy.sh` | ntfy server URL |
| `EOL_TOOL_NTFY_TOPIC` | *(none)* | ntfy topic name |
| `EOL_TOOL_NTFY_TOKEN` | *(none)* | ntfy auth token |
| `EOL_TOOL_SCHEDULE_INTERVAL` | `24` | Check interval in hours |
| `EOL_TOOL_RETRY_MAX` | `3` | Max retries for HTTP requests |
| `EOL_TOOL_RETRY_BASE_DELAY` | `2.0` | Base delay in seconds for exponential backoff |

## Input Format

eol-tool accepts xlsx files with these columns:

| Column | Required | Example |
|--------|----------|---------|
| Model | Yes | `EX4300-48T`, `EPYC 7413`, `PM893`, `R630` |
| Manufacturer | Yes | `Juniper`, `AMD`, `Samsung`, `Dell` |
| Category | Yes | `switch`, `cpu`, `ssd`, `server`, `memory`, `nic`, `hdd` |

A pre-formatted template with example rows is available for download in the web UI.

## Adding Manual Overrides

**Via web UI:** Navigate to the Manual Overrides page from the dashboard.

**Via CLI:** Edit `data/manual_overrides.csv` directly. Columns: `model`, `manufacturer`, `status`, `eol_reason`, `risk_category`, `eol_date`, `eos_date`, `source_url`, `notes`.

**Via API:**

```bash
# Create an override
curl -X POST http://localhost:8080/api/overrides \
  -H "Content-Type: application/json" \
  -d '{"model": "EX4300-48T", "manufacturer": "Juniper", "status": "eol"}'

# Import from CSV
curl -X POST http://localhost:8080/api/overrides/import \
  -F "file=@manual_overrides.csv"
```

## Development

```bash
git clone https://github.com/SalMutt/eol-tool.git
cd eol-tool
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev,api]"
playwright install chromium
```

```bash
pytest -v                      # run tests
ruff check src/ tests/         # lint
pytest --cov=eol_tool          # coverage
```

## License

[Apache 2.0](LICENSE)
