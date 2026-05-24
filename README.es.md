<!-- mcp-name: io.github.alcastaro/opendata-latam-mcp -->

**[English](README.md) · [Español](README.es.md)**

---

# opendata-latam-mcp

**Servidor [Model Context Protocol](https://modelcontextprotocol.io) unificado que expone los datos abiertos del gobierno de cada país latinoamericano soportado a través de una sola interfaz.**

Una instalación, seis portales, **11,175+ datasets públicos** de Argentina, Chile, República Dominicana, Ecuador, México y Uruguay — buscables, filtrables y consultables cruzando países desde cualquier asistente de IA compatible con MCP (Claude Desktop, Claude Code, Cursor, Gemini CLI, ChatGPT Desktop).

---

## ¿Qué problema resuelve?

América Latina tiene aproximadamente 10 portales oficiales de datos abiertos. Cada uno habla un dialecto API distinto — CKAN en la mayoría, Socrata en Colombia, Java custom en Brasil. Un periodista comparando ejecución presupuestaria a nivel regional hoy tiene que aprender N APIs distintas y correr N queries separadas.

Este MCP colapsa eso a **un parámetro de código de país**. El modelo decide qué portal consultar, o lanza en paralelo a todos. Ejemplos que funcionan hoy:

- *"¿Cómo se compara el presupuesto del Ministerio de Salud entre Chile, México y República Dominicana en 2024?"*
- *"Listame las 5 instituciones que más publican datasets en cada portal de LatAm."*
- *"Buscá todos los datasets sobre agua publicados en LatAm en el último año."*

La funcionalidad única es `cross_country_search`: una sola llamada consulta todos los portales soportados en paralelo y devuelve resultados unificados en menos de 3 segundos. **Imposible con MCPs single-country.**

## ¿Para quién es?

- **Periodistas de datos regionales** cubriendo múltiples países LatAm.
- **Investigadores y académicos** haciendo política pública comparada.
- **Organismos multilaterales** (ONU, BID, Banco Mundial, OGP) monitoreando compromisos de transparencia regional.
- **Sociedad civil** monitoreando rendición de cuentas gubernamental transfronteriza.
- **Desarrolladores** construyendo aplicaciones civic-tech que necesitan acceso normalizado a datos LatAm.

## Por qué existe

Inspirado en [`dominican-open-data-mcp`](https://github.com/alcastaro/datos.gob.do-MCP-server) (el MCP single-country que probó el patrón), `opendata-latam-mcp` lo generaliza vía arquitectura adapter-pattern: cada portal hereda de una interface común `PortalAdapter`, así el mismo set de tools MCP funciona contra cualquier país.

## Países soportados (v0.1.0)

| País | Portal | Plataforma | Datasets verificados |
|---|---|---|---|
| 🇦🇷 Argentina | [`datos.gob.ar`](https://datos.gob.ar) | CKAN 2.7.6 | 1,234 |
| 🇨🇱 Chile | [`datos.gob.cl`](https://datos.gob.cl) | CKAN (con DataStore) | 2,990 |
| 🇩🇴 República Dominicana | [`datos.gob.do`](https://datos.gob.do) | CKAN 2.11.3 | 1,054 |
| 🇪🇨 Ecuador | [`datosabiertos.gob.ec`](https://www.datosabiertos.gob.ec) | CKAN 2.9.3 | 1,573 |
| 🇲🇽 México | [`datos.gob.mx`](https://www.datos.gob.mx) | CKAN (con DataStore + xloader) | 1,645 |
| 🇺🇾 Uruguay | [`catalogodatos.gub.uy`](https://catalogodatos.gub.uy) | CKAN (con DataStore + DCAT) | 2,679 |
| **TOTAL** | | | **11,175** |

**Roadmap:** Colombia (Socrata, ~10k datasets) en v0.2 · Brasil (auth custom) en v0.3 · Perú + Bolivia en v0.4.

## Herramientas expuestas

14 tools en total: 11 por país, 2 cross-país, 1 catálogo.

### Catálogo

| Tool | Qué hace |
|---|---|
| `list_supported_countries` | Devuelve la lista de países soportados con nombre del portal, URL y plataforma. Llamala primero si no estás seguro qué códigos son válidos. |

### Por país (requiere código ISO 3166-1 alpha-2)

Cada tool acepta un parámetro `country`: `AR`, `CL`, `DO`, `EC`, `MX`, `UY`.

| Tool | Qué hace |
|---|---|
| `search_datasets` | Busca por keyword, organización, tag o grupo dentro de un país. |
| `get_dataset` | Metadatos completos de un dataset incluyendo todos sus recursos descargables. |
| `list_recent_datasets` | Datasets modificados más recientemente en el portal del país. |
| `get_resource` | Metadatos de un recurso individual (URL, formato, tamaño, fecha). |
| `search_resources` | Busca recursos por nombre dentro de un país. |
| `list_organizations` | Instituciones publicadoras con conteo de datasets por organización. |
| `get_organization` | Info detallada de una sola institución. |
| `list_groups` | Categorías temáticas con conteos. |
| `list_tags` | Tags disponibles, opcionalmente filtrados por prefijo. |
| `autocomplete` | Resuelve nombres parciales de datasets, organizaciones, grupos o tags. |
| `get_site_stats` | Conteos portal-wide (datasets, organizaciones, grupos, tags). |

### Cross-country (el value-add único)

| Tool | Qué hace |
|---|---|
| `cross_country_search` | Busca el mismo término en todos (o seleccionados) los portales de LatAm en paralelo. Devuelve breakdown por país + total grand. |
| `cross_country_stats` | Corre `get_site_stats` contra todos los países soportados en paralelo. Health check rápido + tamaños comparativos. |

---

## Instalación y configuración

### Opción A — Vía `uvx` desde PyPI

Una vez que v0.1.0 esté publicado en PyPI:

```bash
uvx --from opendata-latam-mcp opendata-latam-mcp
```

### Opción B — Vía `uvx` desde GitHub (dev más reciente)

```bash
uvx --from git+https://github.com/alcastaro/opendata-latam-mcp.git opendata-latam-mcp
```

Requisito: [`uv`](https://docs.astral.sh/uv/) instalado.

### Opción C — Clone local para desarrollo

```bash
git clone https://github.com/alcastaro/opendata-latam-mcp.git
cd opendata-latam-mcp
uv sync --extra dev
uv run opendata-latam-mcp
```

### Claude Desktop

Editá `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) o `%APPDATA%\Claude\claude_desktop_config.json` (Windows):

```json
{
  "mcpServers": {
    "opendata-latam": {
      "command": "/Users/TU_USUARIO/.local/bin/uvx",
      "args": [
        "--from",
        "git+https://github.com/alcastaro/opendata-latam-mcp.git",
        "opendata-latam-mcp"
      ]
    }
  }
}
```

Cerrá Claude Desktop completo (Cmd+Q en macOS, Quit desde bandeja sistema en Windows) y reabrí.

### Claude Code

```bash
claude mcp add opendata-latam -- uvx --from git+https://github.com/alcastaro/opendata-latam-mcp.git opendata-latam-mcp
```

### Gemini CLI

Editá `~/.gemini/settings.json`:

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

## Ejemplos de uso

### Un país

> *Usá opendata-latam para buscar datasets sobre transporte en Chile.*

→ `search_datasets(country="CL", query="transporte", limit=10)`.

### Cross-country (el diferenciador)

> *Compará cuántos datasets tiene cada portal de LatAm sobre salud.*

→ `cross_country_search(query="salud", limit_per_country=3)` → devuelve hits por país, total grand, y datasets de muestra de cada uno.

### Tamaños de portales lado-a-lado

> *¿Qué país de LatAm publica más datos abiertos?*

→ `cross_country_stats()` → devuelve Chile 2,990 / Uruguay 2,679 / México 1,645 / Ecuador 1,573 / Argentina 1,234 / República Dominicana 1,054.

### Drill down

> *Encontrá el slug del Ministerio de Salud mexicano y decime cuántos datasets publica.*

→ `autocomplete(country="MX", kind="organization", query="salud")` → `get_organization(country="MX", id=...)`.

---

## Arquitectura

```
src/opendata_latam_mcp/
├── server.py              Entry FastMCP; tools registrados acá
├── countries.py           ISO 3166-1 alpha-2 → metadata país
└── adapters/
    ├── base.py            PortalAdapter Protocol (el contrato)
    ├── registry.py        Código país → adapter singleton
    ├── ckan/
    │   ├── base.py        Cliente CKAN genérico (Solr escape, formatters, todas las operaciones)
    │   ├── argentina.py   Solo override URL
    │   ├── chile.py       Solo override URL
    │   ├── dominican_republic.py
    │   ├── ecuador.py
    │   ├── mexico.py
    │   └── uruguay.py
    └── socrata/           (v0.2 — Colombia)
```

### Decisiones de diseño

- **Adapter pattern como costura.** Cada portal expone el mismo `PortalAdapter` Protocol. Añadir un país = subclasear + un override URL. Los portales CKAN comparten la implementación entera; Socrata y custom se enchufan al mismo registry.
- **Código país como clave primaria.** Cada tool requiere `country` (ISO alpha-2). El modelo siempre sabe qué portal está consultando. Errores son scoped al país que falla.
- **Cross-country es `asyncio.gather`.** Fan-out en paralelo contra N portales, devuelve dict por país + summary. Latencia sub-3-segundos para 6 portales.
- **System trust store para SSL.** Algunos portales LatAm (notablemente `datos.gob.mx`) shipean chains TLS incompletos que `certifi` no puede verificar. `truststore` inyecta el OS trust store, que `curl` ya usa, así httpx los acepta.
- **Truncado defensivo.** Descripciones largas truncadas a 300 chars en listados. Dumps cross-country con 6 países × 10 datasets × descripciones multi-KB volarían context windows sin esto.
- **FastMCP idiomático.** Args tipados con Pydantic; sin schema manual. Cada tool es una función decorada.
- **Logging solo stderr.** Requerido por spec MCP para servers stdio (stdout es el protocol stream).

### Stack

- [`mcp`](https://pypi.org/project/mcp/) (FastMCP) · [`httpx`](https://www.python-httpx.org/) · [`truststore`](https://pypi.org/project/truststore/) · [`duckdb`](https://duckdb.org/) (para layer analytics planeada v0.5) · [`openpyxl`](https://openpyxl.readthedocs.io/) · [`chardet`](https://chardet.readthedocs.io/) · [`odfpy`](https://github.com/eea/odfpy).

---

## Roadmap

- **v0.1** — 6 países CKAN (AR, CL, DO, EC, MX, UY) · cross-country search + stats · este release.
- **v0.2** — Colombia vía Socrata SODA API (10,000+ datasets).
- **v0.3** — Brasil vía adapter custom `dados.gov.br` (Bearer auth).
- **v0.4** — Perú (bypass CloudWAF) y Bolivia (bypass anti-bot).
- **v0.5** — Portar la capa analytics de `dominican-open-data-mcp` (cache DuckDB, `filter_resource`, `aggregate_resource`, `query_resource`) así el mismo escape hatch SQL funciona contra cualquier recurso de portal cacheado.
- **v0.6** — Analytics cross-country: `compare_indicators`, `find_equivalent_datasets`, alineación de series temporales entre países.

Ver [`Roadmap.md`](https://github.com/alcastaro/datos.gob.do-MCP-server/blob/main/Roadmap.md) en el repo RD MCP para el inventario completo de portales LatAm.

## Limitaciones conocidas

- v0.1 devuelve solo metadata. Sin filter/aggregate/SQL hasta v0.5.
- Colombia, Brasil, Perú, Bolivia aún no soportados.
- Queries cross-country son tan lentas como el portal más lento.
- La calidad de datos de cada portal es la que entrega el gobierno publicador; este MCP no normaliza schemas entre países (planeado para v0.6).

## Contribuciones

Pull requests bienvenidos. La forma más rápida de añadir valor: shipear un nuevo adapter de país. Portales CKAN son típicamente un archivo (~5 líneas, override URL). Portales no-CKAN necesitan un cliente nuevo implementando el `PortalAdapter` Protocol.

## Créditos

Construido por [@alcastaro](https://github.com/alcastaro). Inspirado en [`datagouv-mcp`](https://github.com/datagouv/datagouv-mcp) (Etalab, Francia) y [`dominican-open-data-mcp`](https://github.com/alcastaro/datos.gob.do-MCP-server) (el MCP single-country previo del mismo autor).

## Licencia

MIT para el código fuente. Datos accedidos a través de este MCP son publicados independientemente por cada gobierno bajo sus propios términos (típicamente ODbL o Creative Commons). Ver [LICENSE](LICENSE).
