# Test Fixtures

This directory contains captured HTTP responses and sample data used by tests.

## Capturing fixtures

1. Run the real checker against the vendor site
2. Save the raw HTML/JSON response to a file named `{vendor}_{model}.html` or `.json`
3. Reference the fixture in your test with `pathlib.Path(__file__).parent / "fixtures" / "filename"`

Fixtures should be committed to version control so tests remain reproducible
without network access.
