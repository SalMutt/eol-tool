# Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability in eol-tool, please report it by opening a private issue or emailing the maintainer.

## Data Privacy

eol-tool processes hardware model information only. When using the web UI:

- File uploads are processed server-side and not stored permanently
- Single-model lookups query external APIs (Intel ARK, Juniper, Cisco, endoflife.date)
- No personal data is collected or transmitted
- All scraped data is cached locally in SQLite

## External Connections

eol-tool makes outbound connections to:

- endoflife.date API (HTTPS)
- ark.intel.com (HTTPS, via Playwright)
- cisco.com (HTTPS, via Playwright)
- support.juniper.net (HTTPS)

No data from your inventory is sent to these services — only model names are used as search queries.
