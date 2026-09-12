<!-- mcp-name: io.github.alcastaro/opendata-latam-mcp -->

**[English](README.md) · [Español](README.es.md)**

---

# opendata-latam-mcp

**A unified [Model Context Protocol](https://modelcontextprotocol.io) server that exposes the open government data of every supported Latin American country through a single interface.**

One install, six live portals, **15,628 public datasets** from Argentina, Chile, Dominican Republic, Mexico, Panama, and Uruguay — searchable and cross-country queryable from any MCP-compatible AI assistant (Claude Desktop, Claude Code, Cursor, Gemini CLI, ChatGPT Desktop).

> **Read this before anything else:** fourteen of the fifteen tools are **catalogue-level** — they find datasets and describe them. Only `read_resource_rows` returns rows, and only where the portal has built a CKAN DataStore table for that resource (measured: 64.5% of sampled datasets across five portals). No file download, no parsing. See [Scope: what this does and does not do](#scope-what-this-does-and-does-not-do).

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

This project did not start regional. It started with **two single-country servers,
built deliberately, one per platform** — because the only way to learn what a portal
family can actually do is to take one country all the way down.

- [**`dominican-open-data-mcp`**](https://github.com/alcastaro/datos.gob.do-MCP-server)
  covered **CKAN**, and the hardest variant of it: `datos.gob.do` runs CKAN *without*
  the DataStore extension, so no query is possible and every row has to come out of a
  downloaded file. That is where the download, encoding-detection, link-repair and
  DuckDB layers were written and measured.
- **`colombian-open-data-mcp`** covered **Socrata** — `datos.gov.co` and its SoQL query
  language, with `WHERE`, `GROUP BY` and aggregation running on the server. It also
  picked up four CKAN municipal portals *with* DataStore along the way, plus ArcGIS REST
  services, which is how the three-route chain (DataStore → ArcGIS service → published
  file) was found.

Between them, those two servers cover the two platforms that most of Latin America
runs on, at real depth, measured against live portals rather than assumed. Everything
that was learned doing it is written down and is what this repository is built from.

`opendata-latam-mcp` generalizes that work through an adapter-pattern architecture:
every portal subclasses a common `PortalAdapter` interface, so the same set of MCP
tools works against any country. **The two country servers are not being replaced —
they will be imported as libraries**, so a fix in the shared security code reaches
every server at once instead of having to be applied three times.

## Supported countries

Counts below were **measured on 2026-08-30 by calling the registered tools against
the live portals**, not read off a catalogue flag. They move as the portals publish.

| Country | Portal | Platform | Datasets |
|---|---|---|---|
| 🇵🇦 Panama | [`datosabiertos.gob.pa`](https://datosabiertos.gob.pa) | CKAN 2.11.2 (with DataStore) | 5,667 |
| 🇨🇱 Chile | [`datos.gob.cl`](https://datos.gob.cl) | CKAN (with DataStore) | 3,188 |
| 🇺🇾 Uruguay | [`catalogodatos.gub.uy`](https://catalogodatos.gub.uy) | CKAN (with DataStore + DCAT) | 2,702 |
| 🇲🇽 Mexico | [`datos.gob.mx`](https://www.datos.gob.mx) | CKAN (with DataStore + xloader) | 1,736 |
| 🇦🇷 Argentina | [`datos.gob.ar`](https://datos.gob.ar) | CKAN 2.7.6 | 1,273 |
| 🇩🇴 Dominican Republic | [`datos.gob.do`](https://datos.gob.do) | CKAN 2.11.3 (no DataStore) | 1,062 |
| **TOTAL live** | | | **15,628** |
| 🇪🇨 Ecuador | [`datosabiertos.gob.ec`](https://www.datosabiertos.gob.ec) | CKAN 2.9.3 | **unavailable** |

**Ecuador is configured but not answering.** Since 2026-08-30 the portal returns
HTTP 403 to every request — with any User-Agent, with none, and on the site root as
well as the API. It is kept in the list rather than deleted because one vantage point
cannot distinguish a portal that closed programmatic access from one that blocks a
particular address. Tools targeting `EC` return an error, not results.

**Next:** Colombia (5 portals, 2 platforms, ~11k datasets) via the
`colombian-open-data-mcp` package · Peru and Paraguay via a DKAN adapter · Brazil
(Bearer token).

## Scope: what this does and does not do

**Fourteen of the fifteen tools find; one reads.** The fourteen work on the
*catalogue*: they search datasets, return their metadata, and list the organizations,
groups and tags a portal publishes. `read_resource_rows` is the exception — it returns
actual rows, through the portal's CKAN DataStore, wherever the portal has built one for
that resource. There is still no file download and no CSV/XLSX parsing here.

**How far the row reading reaches, measured 2026-08-30** by calling the registered tool
against 40 datasets per country, sampled one per catalogue offset rather than in pages:

| Country | Datasets sampled | Returned rows | Coverage |
|---|---|---|---|
| Mexico | 40 | 39 | 97.5% |
| Uruguay | 40 | 38 | 95.0% |
| Argentina | 40 | 26 | 65.0% |
| Chile | 40 | 15 | 37.5% |
| Panama | 40 | 11 | 27.5% |
| **All five** | **200** | **129** | **64.5%** |

Reproduce it with `uv run python -m opendata_latam_mcp.sweep --countries AR,CL,MX,PA,UY
--per-country 40 --seed 42`. The gap is not a bug: the DataStore covers a fraction of
any catalogue, and everything else is published as a plain file. Panama is the sharpest
case — the largest catalogue here and the lowest coverage, so size and readability do
not travel together.

**It does not aggregate, and that is a measurement rather than an omission.**
`datastore_search_sql`, the CKAN action that would run a `GROUP BY` on the portal, was
tried against six national portals on 2026-08-30 and answers only on Uruguay; everywhere
else it is HTTP 400. Minimum, maximum, average and `GROUP BY` therefore cannot be pushed
to a portal and belong in a local layer above these rows. That is exactly why the
Dominican server has a DuckDB layer — it was the only option, not a preference.

That matters because most of these portals publish the same dataset several ways, and
only some of those ways are a queryable table. Reading rows properly means chaining
three routes — the CKAN DataStore, then an ArcGIS REST service, then the published
file — and stopping at the first that returns rows. That work exists, and it lives in
the two dedicated country packages:

| | Depth | What it can do |
|---|---|---|
| [`dominican-open-data-mcp`](https://github.com/alcastaro/datos.gob.do-MCP-server) | Deep | Downloads the published file, parses it, repairs dead links, and queries it with SQL through DuckDB. Its portal has **no DataStore**, so every row has to come out of a file. |
| `colombian-open-data-mcp` | Deep | Three chained routes — CKAN DataStore → ArcGIS REST service → published file. Measured coverage: 100% nationally, 89.2% for Bogotá. |

Those two will be **imported** into this server rather than reimplemented, so a fix in
the shared code reaches every server at once. Until then, the honest description of
this one is: it tells you which datasets exist across Latin America and where they
are. Saying so in the tool descriptions is deliberate — a server that claims a depth
it does not have costs the model a turn to find out.

**The server stores nothing.** No cache, no mirror, no copies of anyone's data.
Keeping these datasets would make whoever runs it a data controller under Colombia's
Ley 1581 and its equivalents elsewhere. That is a decision taken on purpose, not a
side effect of not having built a cache yet.

## Tools exposed

15 tools total: 11 per-country catalogue, 1 per-country row reading, 2 cross-country, 1 catalog.

### Catalog

| Tool | What it does |
|---|---|
| `list_supported_countries` | Returns the list of countries supported with portal name, URL, and platform. Always call this first if unsure which codes are valid. |

### Per-country (ISO 3166-1 alpha-2 code required)

Every tool below accepts a `country` parameter: `AR`, `CL`, `DO`, `EC`, `MX`, `PA`, `UY` (`EC` is configured but unreachable — see above). The list a model actually sees is generated from the registry, so it cannot drift from this one.

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
| `read_resource_rows` | The rows of one resource, through the portal's CKAN DataStore — paginated, free-text filterable, cells truncated. Where the portal built no table it returns an error saying so and what to try instead. |

### Cross-country (the unique value-add)

| Tool | What it does |
|---|---|
| `cross_country_search` | Search the same term across every (or selected) LatAm portal in parallel. Returns a per-country breakdown plus grand-total hits. |
| `cross_country_stats` | Run `get_site_stats` against every supported country in parallel. Quick health-check + comparative portal sizes. |

---

## Installation and configuration

### Option A — Via `uvx` from PyPI

Once the package is published to PyPI (not yet — the repository is the source of truth until then):

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

→ `cross_country_stats()` → returns Panama 5,667 / Chile 3,188 / Uruguay 2,702 / Mexico 1,736 / Argentina 1,273 / Dominican Republic 1,062.

### Drill down

> *Find the slug for the Mexican Health Ministry and tell me how many datasets it publishes.*

→ `autocomplete(country="MX", kind="organization", query="salud")` → `get_organization(country="MX", id=...)`.

---

## Architecture

```
src/opendata_latam_mcp/
├── server.py              MCPServer (SDK v2) entry; the 15 tools registered here
├── countries.py           ISO 3166-1 alpha-2 → country metadata
├── errors.py              The {"error", "hint"} envelope every tool returns
├── netguard.py            SSRF guard on every hop (interim copy of the shared module)
├── sweep.py               Coverage harness — no figure ships without it
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
    │   ├── panama.py
    │   └── uruguay.py
    └── socrata/           (v0.3 — Colombia, imported)
```

### Design decisions

- **Adapter pattern as the seam.** Every portal exposes the same `PortalAdapter` Protocol. Adding a country = subclassing + an URL override. CKAN portals share the entire implementation; Socrata and custom portals plug into the same registry.
- **Country code as primary key.** Every tool requires `country` (ISO alpha-2). The model always knows which portal it's hitting. Errors are scoped to the offending country.
- **Return, never raise — every tool, every failure.** A tool that fails returns
  `{"error": ..., "hint": ...}` as an ordinary result: `error` keeps the portal's own
  message, and `hint` names what to try next. An unsupported country code says to call
  `list_supported_countries`; a portal answering 403 says the refusal is policy rather
  than a bad request, so retrying will not help and `cross_country_search` will report it
  per-country without failing the whole call.

  This is measured, not aspirational. Before it existed, a real client session calling
  `search_datasets` with a bad country received exactly `Error executing tool
  search_datasets` and nothing else — the SDK discards the underlying message. A model
  given that cannot tell a bad argument from a dead portal, so it retries blindly.
- **Every tool returns an object, never a bare list.** That is what makes the envelope
  possible: the SDK derives an output schema from the return type and rejects a mismatched
  shape, so a tool returning a bare list could not return an error envelope. Lists live
  under a named key (`groups`, `tags`, `suggestions`), which also gives the model the
  portal context a bare list never carried.
- **Portal health is machine-readable.** `list_supported_countries` reports a `status` per
  portal, so a model can route around one that is down instead of spending a turn
  discovering it.
- **Cross-country is `asyncio.gather`.** Fan-out in parallel against N portals, return a per-country dict + a summary. Sub-3-second latency across all portals. A portal that fails returns its error inside the result; it does not take the others down.
- **System trust store for SSL.** Some LatAm portals (notably `datos.gob.mx`) ship incomplete TLS cert chains that `certifi` can't verify. `truststore` injects the OS trust store, which `curl` already uses, so httpx accepts them.
- **Defensive truncation.** Long descriptions truncated to 300 chars in listings. Cross-country dumps with 6 countries × 10 datasets × multi-KB descriptions would blow context windows without this.
- **Idiomatic MCP SDK v2 (`MCPServer`).** Pydantic-typed args and an object output schema on every tool; no manual schema. Every tool is one decorated function, wrapped in the error envelope.
- **stderr-only logging.** Required by MCP spec for stdio servers (stdout is the protocol stream).

### Stack

- [`mcp`](https://pypi.org/project/mcp/) (SDK v2, `>=2.1,<3`) · [`httpx`](https://www.python-httpx.org/) · [`truststore`](https://pypi.org/project/truststore/). Three runtime dependencies, deliberately: the file-parsing and DuckDB stack arrives with the imported country packages in v0.5, not before.

---

## Roadmap

- **v0.1** (shipped 2026-05) — 6 CKAN countries · cross-country search + stats.
- **v0.2** (this release) — Panama · MCP SDK v2 · reading rows through the CKAN
  DataStore, measured rather than assumed (table above) · an actionable
  `{"error", "hint"}` from every tool instead of an opaque protocol error · SSRF
  guard on every redirect hop.
- **v0.3** — Colombia through the `colombian-open-data-mcp` package: 5 portals across
  2 platforms (Socrata nationally, CKAN for Bogotá, Cali, Valle del Cauca, Cartagena).
  Imported as a library, not copied, so a fix in the shared security code reaches
  every server that uses it. Retries arrive the same way.
- **v0.4** — Peru and Paraguay through a DKAN adapter. **Peru is not "CloudWAF-protected"** —
  that earlier claim was wrong, and measurement on 2026-08-30 disproved it. Peru runs
  DKAN on Drupal 7 and serves a *partial* CKAN action API: `package_list` (4,670
  datasets), `package_show` and `group_list` work, while `package_search`,
  `organization_list`, `tag_list` and `resource_search` all return 404. There is no
  server-side search, so any search over Peru is client-side and will say so.
- **v0.4+** — Brazil (`dados.gov.br`, Bearer token via developer registration).
  Bolivia and Guatemala answer HTTP 403 to everything; **this project does not
  impersonate a browser to get past a WAF**, so they stay unsupported unless they
  open up.
- **v0.5** — Aggregation over whole resources, computed locally in DuckDB with the engine
  imported from `dominican-open-data-mcp`. Local because it has to be: `datastore_search_sql`
  answers on Uruguay alone, so no portal here can run a `GROUP BY` for us. Still no cache
  on disk — rows are held for the call and discarded.
- **v0.6** — Cross-country analytics: `compare_indicators`, `find_equivalent_datasets`, time-series alignment across countries.

See [`Roadmap.md`](https://github.com/alcastaro/datos.gob.do-MCP-server/blob/main/Roadmap.md) in the RD MCP repo for the full LatAm portal inventory.

## Known limitations

- Rows come only through the CKAN DataStore, which covers a fraction of every catalogue
  (64.5% of sampled datasets across five portals; none in the Dominican Republic). No
  file download or parsing yet — see the scope section above.
- Ecuador is unreachable; Colombia, Brazil, Peru, Paraguay and Bolivia are not yet supported.
- Cross-country queries are as slow as the slowest single portal.
- Each portal's data quality is whatever the publishing government provides; this MCP doesn't normalize schemas across countries (that's planned for v0.6).

## Contributing

Pull requests welcome. The fastest way to add value: ship a new country adapter. CKAN portals are typically one file (~5 lines, URL override). Non-CKAN portals need a fresh client implementing the `PortalAdapter` Protocol.

## Credits

Built by [@alcastaro](https://github.com/alcastaro). Inspired by [`datagouv-mcp`](https://github.com/datagouv/datagouv-mcp) (Etalab, France) and [`dominican-open-data-mcp`](https://github.com/alcastaro/datos.gob.do-MCP-server) (this author's earlier single-country MCP).

## License

MIT for the source code. Data accessed through this MCP is published independently by each country's government under its own terms (commonly ODbL or Creative Commons). See [LICENSE](LICENSE).
