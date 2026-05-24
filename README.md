<!-- mcp-name: io.github.alcastaro/opendata-latam-mcp -->

**[English](README.md) · [Español](README.es.md)**

---

# opendata-latam-mcp

**A unified [Model Context Protocol](https://modelcontextprotocol.io) server that exposes the open government data of every supported Latin American country through a single interface.**

One install, six portals, **11,175+ public datasets** from Argentina, Chile, Dominican Republic, Ecuador, Mexico, and Uruguay — searchable, filterable, and cross-country queryable from any MCP-compatible AI assistant (Claude Desktop, Claude Code, Cursor, Gemini CLI, ChatGPT Desktop).

---

## What problem does it solve?

Latin America has ~10 official open-data portals across its countries. Each speaks a different API dialect — CKAN in most, Socrata in Colombia, custom Java in Brazil. A journalist comparing budget execution across the region today has to learn N different APIs and run N separate queries.

This MCP collapses that to **one country code parameter**. The model decides which portal to hit, or fans out to all of them in parallel. Examples that work today:

- *"How does the Ministry of Health budget compare between Chile, Mexico, and the Dominican Republic in 2024?"*
- *"List the 5 most-published institutions in each LatAm portal."*
- *"Find every dataset about water across LatAm published in the last year."*

The unique feature is `cross_country_search`: a single tool call queries every supported portal in parallel and returns a unified result set in under 3 seconds. **This is impossible with single-country MCPs.**

## Who is it for?

- **Regional data journalists** covering multiple LatAm countries.
- **Researchers and academics** doing comparative public-policy work.
- **Multilateral organizations** (UN, IDB, World Bank, OGP) tracking transparency commitments across the region.
- **Civil society** monitoring government accountability cross-border.
- **Developers** building civic-tech applications that need normalized LatAm data access.

## Why this exists

Inspired by [`dominican-open-data-mcp`](https://github.com/alcastaro/datos.gob.do-MCP-server) (the single-country MCP that proved the pattern), `opendata-latam-mcp` generalizes it through an adapter-pattern architecture: every portal subclasses a common `PortalAdapter` interface, so the same set of MCP tools works against any country.

## Supported countries (v0.1.0)

| Country | Portal | Platform | Datasets verified |
|---|---|---|---|
| 🇦🇷 Argentina | [`datos.gob.ar`](https://datos.gob.ar) | CKAN 2.7.6 | 1,234 |
| 🇨🇱 Chile | [`datos.gob.cl`](https://datos.gob.cl) | CKAN (with DataStore) | 2,990 |
| 🇩🇴 Dominican Republic | [`datos.gob.do`](https://datos.gob.do) | CKAN 2.11.3 | 1,054 |
| 🇪🇨 Ecuador | [`datosabiertos.gob.ec`](https://www.datosabiertos.gob.ec) | CKAN 2.9.3 | 1,573 |
| 🇲🇽 Mexico | [`datos.gob.mx`](https://www.datos.gob.mx) | CKAN (with DataStore + xloader) | 1,645 |
| 🇺🇾 Uruguay | [`catalogodatos.gub.uy`](https://catalogodatos.gub.uy) | CKAN (with DataStore + DCAT) | 2,679 |
| **TOTAL** | | | **11,175** |

**Roadmap:** Colombia (Socrata, ~10k datasets) in v0.2 · Brazil (custom auth) in v0.3 · Peru + Bolivia in v0.4.

## Tools exposed

14 tools total: 11 per-country, 2 cross-country, 1 catalog.

### Catalog

| Tool | What it does |
|---|---|
| `list_supported_countries` | Returns the list of countries supported with portal name, URL, and platform. Always call this first if unsure which codes are valid. |

### Per-country (ISO 3166-1 alpha-2 code required)

Every tool below accepts a `country` parameter: `AR`, `CL`, `DO`, `EC`, `MX`, `UY`.

| Tool | What it does |
|---|---|
| `search_datasets` | Search by keyword, organization, tag, or group within one country. |
| `get_dataset` | Full metadata for a dataset including all downloadable resources. |
| `list_recent_datasets` | Most recently modified datasets in a country's portal. |
| `get_resource` | Metadata for a single resource (URL, format, size, date). |
| `search_resources` | Search resources by name within one country. |
| `list_organizations` | Publishing institutions with per-org dataset count. |
| `get_organization` | Detailed info on a single institution. |
| `list_groups` | Thematic categories with counts. |
| `list_tags` | Tags available, optionally prefix-filtered. |
| `autocomplete` | Resolve partial names for datasets, organizations, groups, or tags. |
| `get_site_stats` | Portal-wide counts (datasets, organizations, groups, tags). |

### Cross-country (the unique value-add)

| Tool | What it does |
|---|---|
| `cross_country_search` | Search the same term across every (or selected) LatAm portal in parallel. Returns a per-country breakdown plus grand-total hits. |
| `cross_country_stats` | Run `get_site_stats` against every supported country in parallel. Quick health-check + comparative portal sizes. |

---

## Installation and configuration

### Option A — Via `uvx` from PyPI

Once v0.1.0 is published to PyPI:

```bash
uvx --from opendata-latam-mcp opendata-latam-mcp
```

### Option B — Via `uvx` from GitHub (latest dev)

```bash
uvx --from git+https://github.com/alcastaro/opendata-latam-mcp.git opendata-latam-mcp
```

Prerequisite: [`uv`](https://docs.astral.sh/uv/) installed.

### Option C — Local clone for development

```bash
git clone https://github.com/alcastaro/opendata-latam-mcp.git
cd opendata-latam-mcp
uv sync --extra dev
uv run opendata-latam-mcp
```

### Claude Desktop configuration

Edit `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) or `%APPDATA%\Claude\claude_desktop_config.json` (Windows):

```json
{
  "mcpServers": {
    "opendata-latam": {
      "command": "/Users/YOUR_USERNAME/.local/bin/uvx",
      "args": [
        "--from",
        "git+https://github.com/alcastaro/opendata-latam-mcp.git",
        "opendata-latam-mcp"
      ]
    }
  }
}
```

Quit Claude Desktop fully (Cmd+Q on macOS, Quit from system tray on Windows) and reopen.

### Claude Code

```bash
claude mcp add opendata-latam -- uvx --from git+https://github.com/alcastaro/opendata-latam-mcp.git opendata-latam-mcp
```

### Gemini CLI

Edit `~/.gemini/settings.json`:

```json
{
  "mcpServers": {
    "opendata-latam": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/alcastaro/opendata-latam-mcp.git", "opendata-latam-mcp"]
    }
  }
}
```

---

## Usage examples

### Single country

> *Use opendata-latam to search datasets about transport in Chile.*

→ `search_datasets(country="CL", query="transporte", limit=10)`.

### Cross-country (the differentiator)

> *Compare how many datasets each LatAm portal has about health.*

→ `cross_country_search(query="salud", limit_per_country=3)` → returns hits per country, grand total, and sample datasets from each.

### Portal sizes side-by-side

> *Which LatAm country publishes the most open data?*

→ `cross_country_stats()` → returns Chile 2,990 / Uruguay 2,679 / Mexico 1,645 / Ecuador 1,573 / Argentina 1,234 / Dominican Republic 1,054.

### Drill down

> *Find the slug for the Mexican Health Ministry and tell me how many datasets it publishes.*

→ `autocomplete(country="MX", kind="organization", query="salud")` → `get_organization(country="MX", id=...)`.

---

## Architecture

```
src/opendata_latam_mcp/
├── server.py              FastMCP entry; tools registered here
├── countries.py           ISO 3166-1 alpha-2 → country metadata
└── adapters/
    ├── base.py            PortalAdapter Protocol (the contract)
    ├── registry.py        Country code → adapter singleton
    ├── ckan/
    │   ├── base.py        Generic CKAN client (Solr escape, formatters, all ops)
    │   ├── argentina.py   URL override only
    │   ├── chile.py       URL override only
    │   ├── dominican_republic.py
    │   ├── ecuador.py
    │   ├── mexico.py
    │   └── uruguay.py
    └── socrata/           (v0.2 — Colombia)
```

### Design decisions

- **Adapter pattern as the seam.** Every portal exposes the same `PortalAdapter` Protocol. Adding a country = subclassing + an URL override. CKAN portals share the entire implementation; Socrata and custom portals plug into the same registry.
- **Country code as primary key.** Every tool requires `country` (ISO alpha-2). The model always knows which portal it's hitting. Errors are scoped to the offending country.
- **Cross-country is `asyncio.gather`.** Fan-out in parallel against N portals, return a per-country dict + a summary. Sub-3-second latency for 6 portals.
- **System trust store for SSL.** Some LatAm portals (notably `datos.gob.mx`) ship incomplete TLS cert chains that `certifi` can't verify. `truststore` injects the OS trust store, which `curl` already uses, so httpx accepts them.
- **Defensive truncation.** Long descriptions truncated to 300 chars in listings. Cross-country dumps with 6 countries × 10 datasets × multi-KB descriptions would blow context windows without this.
- **Idiomatic FastMCP.** Pydantic-typed args; no manual schema. Every tool is one decorated function.
- **stderr-only logging.** Required by MCP spec for stdio servers (stdout is the protocol stream).

### Stack

- [`mcp`](https://pypi.org/project/mcp/) (FastMCP) · [`httpx`](https://www.python-httpx.org/) · [`truststore`](https://pypi.org/project/truststore/) · [`duckdb`](https://duckdb.org/) (for the planned v0.5 analytics layer) · [`openpyxl`](https://openpyxl.readthedocs.io/) · [`chardet`](https://chardet.readthedocs.io/) · [`odfpy`](https://github.com/eea/odfpy).

---

## Roadmap

- **v0.1** — 6 CKAN countries (AR, CL, DO, EC, MX, UY) · cross-country search + stats · this release.
- **v0.2** — Colombia via Socrata SODA API (10,000+ datasets).
- **v0.3** — Brazil via custom `dados.gov.br` adapter (Bearer auth).
- **v0.4** — Peru (CloudWAF bypass) and Bolivia (anti-bot bypass).
- **v0.5** — Port the analytics layer from `dominican-open-data-mcp` (DuckDB cache, `filter_resource`, `aggregate_resource`, `query_resource`) so the same SQL escape hatch works against every cached portal resource.
- **v0.6** — Cross-country analytics: `compare_indicators`, `find_equivalent_datasets`, time-series alignment across countries.

See [`Roadmap.md`](https://github.com/alcastaro/datos.gob.do-MCP-server/blob/main/Roadmap.md) in the RD MCP repo for the full LatAm portal inventory.

## Known limitations

- v0.1 returns metadata only. No filter/aggregate/SQL until v0.5.
- Colombia, Brazil, Peru, Bolivia are not yet supported.
- Cross-country queries are as slow as the slowest single portal.
- Each portal's data quality is whatever the publishing government provides; this MCP doesn't normalize schemas across countries (that's planned for v0.6).

## Contributing

Pull requests welcome. The fastest way to add value: ship a new country adapter. CKAN portals are typically one file (~5 lines, URL override). Non-CKAN portals need a fresh client implementing the `PortalAdapter` Protocol.

## Credits

Built by [@alcastaro](https://github.com/alcastaro). Inspired by [`datagouv-mcp`](https://github.com/datagouv/datagouv-mcp) (Etalab, France) and [`dominican-open-data-mcp`](https://github.com/alcastaro/datos.gob.do-MCP-server) (this author's earlier single-country MCP).

## License

MIT for the source code. Data accessed through this MCP is published independently by each country's government under its own terms (commonly ODbL or Creative Commons). See [LICENSE](LICENSE).
