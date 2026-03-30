# Contributing to eol-tool

## Development Setup

```bash
git clone https://github.com/SalMutt/eol-tool.git
cd eol-tool
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest -v
```

## Adding a New Vendor Checker

1. Create `src/eol_tool/checkers/vendorname.py`
2. Extend `BaseChecker`, set `manufacturer_name` to the vendor name
3. Implement the async `check` method returning an `EOLResult`
4. If the vendor has a scrapable EOL page, use Playwright and set `date_source` to `manufacturer_confirmed`
5. If no EOL data source exists, use classification rules and set `date_source` to `none`
6. Add tests in `tests/test_checkers/test_vendorname.py`
7. Run `pytest -v` and `ruff check src/ tests/`

## Scraper Guidelines

- Every HTTP call must have `timeout=10.0`
- Every HTTP call must be wrapped in `try/except` with graceful fallback
- Playwright scrapers must launch headless and close after batch
- Cache all scraped results in SQLite with appropriate TTL
- Log at INFO level before and after HTTP requests
- Log at WARNING level on failures

## Code Style

- ruff for linting
- Type hints on all public functions
- Async checkers using httpx or Playwright
- No hardcoded EOL dates in checker code

## Testing

- All tests run with: `pytest -v`
- Tests marked with `@pytest.mark.playwright` are skipped when Playwright is not installed
- Mock HTTP calls in tests, do not hit real vendor sites
- Use test fixtures in `tests/fixtures/` for HTML page samples

## Cache Management

- All scraped data cached in SQLite at `~/.cache/eol-tool/`
- Clear cache during development: `eol-tool cache clear`
- Refresh from live sources: `eol-tool update`
