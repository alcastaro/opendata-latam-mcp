<!-- mcp-name: io.github.alcastaro/opendata-latam-mcp -->

**[English](README.md) · [Español](README.es.md)**

---

# opendata-latam-mcp

**Servidor [Model Context Protocol](https://modelcontextprotocol.io) unificado que expone los datos abiertos del gobierno de cada país latinoamericano soportado a través de una sola interfaz.**

Una instalación, seis portales vivos, **15.628 datasets públicos** de Argentina, Chile, México, Panamá, República Dominicana y Uruguay — buscables y consultables cruzando países desde cualquier asistente de IA compatible con MCP (Claude Desktop, Claude Code, Cursor, Gemini CLI, ChatGPT Desktop).

> **Léase esto antes que nada:** todas las herramientas son de **nivel catálogo**. Encuentran datasets y los describen; **no leen sus filas.** Ver [Alcance: qué hace y qué no hace](#alcance-qué-hace-y-qué-no-hace).

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

Este proyecto no empezó siendo regional. Empezó con **dos servidores de un solo país,
construidos a propósito, uno por plataforma** — porque la única forma de aprender qué
puede hacer de verdad una familia de portales es llevar un país hasta el fondo.

- [**`dominican-open-data-mcp`**](https://github.com/alcastaro/datos.gob.do-MCP-server)
  cubrió **CKAN**, y en su variante más dura: `datos.gob.do` corre CKAN *sin* la
  extensión DataStore, así que no hay consulta posible y cada fila tiene que salir de un
  archivo descargado. Ahí se escribieron y se midieron las capas de descarga, detección
  de codificación, reparación de enlaces y DuckDB.
- **`colombian-open-data-mcp`** cubrió **Socrata** — `datos.gov.co` y su lenguaje de
  consulta SoQL, con `WHERE`, `GROUP BY` y agregación corriendo en el servidor. De paso
  recogió cuatro portales CKAN municipales *con* DataStore, más servicios ArcGIS REST,
  que es como se descubrió la cadena de tres vías (DataStore → servicio ArcGIS →
  archivo publicado).

Entre los dos cubren las dos plataformas sobre las que corre casi toda América Latina,
a profundidad real y medida contra portales en vivo, no supuesta. Todo lo aprendido
haciéndolo está escrito y es la base de este repositorio.

`opendata-latam-mcp` generaliza ese trabajo mediante una arquitectura de adaptadores:
cada portal hereda de una interfaz común `PortalAdapter`, así el mismo conjunto de
herramientas MCP funciona contra cualquier país. **Los dos servidores de país no se
reemplazan — se importarán como bibliotecas**, para que un arreglo en el código de
seguridad compartido llegue a todos a la vez en vez de tener que aplicarse tres veces.

## Países soportados

Las cifras de abajo se **midieron el 30-ago-2026 invocando las herramientas registradas
contra los portales en vivo**, no leyendo una bandera del catálogo. Cambian a medida que
los portales publican.

| País | Portal | Plataforma | Datasets |
|---|---|---|---|
| 🇵🇦 Panamá | [`datosabiertos.gob.pa`](https://datosabiertos.gob.pa) | CKAN 2.11.2 (con DataStore) | 5.667 |
| 🇨🇱 Chile | [`datos.gob.cl`](https://datos.gob.cl) | CKAN (con DataStore) | 3.188 |
| 🇺🇾 Uruguay | [`catalogodatos.gub.uy`](https://catalogodatos.gub.uy) | CKAN (con DataStore + DCAT) | 2.702 |
| 🇲🇽 México | [`datos.gob.mx`](https://www.datos.gob.mx) | CKAN (con DataStore + xloader) | 1.736 |
| 🇦🇷 Argentina | [`datos.gob.ar`](https://datos.gob.ar) | CKAN 2.7.6 | 1.273 |
| 🇩🇴 República Dominicana | [`datos.gob.do`](https://datos.gob.do) | CKAN 2.11.3 (sin DataStore) | 1.062 |
| **TOTAL vivo** | | | **15.628** |
| 🇪🇨 Ecuador | [`datosabiertos.gob.ec`](https://www.datosabiertos.gob.ec) | CKAN 2.9.3 | **no disponible** |

**Ecuador está configurado pero no responde.** Desde el 30-ago-2026 el portal devuelve
HTTP 403 a toda petición — con cualquier User-Agent, sin ninguno, y tanto en la raíz del
sitio como en el API. Se mantiene en la lista en vez de borrarlo porque un solo punto de
observación no permite distinguir un portal que cerró el acceso programático de uno que
bloquea una dirección concreta. Las herramientas con `EC` devuelven un error, no resultados.

**Lo que sigue:** Colombia (5 portales, 2 plataformas, ~11k datasets) vía el paquete
`colombian-open-data-mcp` · Perú y Paraguay vía un adaptador DKAN · Brasil (token Bearer).

## Alcance: qué hace y qué no hace

**Catorce de las quince herramientas buscan; una lee.** Las catorce trabajan sobre el
*catálogo*: buscan datasets, devuelven sus metadatos y listan las organizaciones, grupos
y etiquetas que publica un portal. `read_resource_rows` es la excepción — devuelve filas
de verdad, a través del DataStore de CKAN del portal, allí donde el portal haya construido
una tabla para ese recurso. Sigue sin haber descarga de archivos ni parseo de CSV o XLSX.

**Hasta dónde llega esa lectura, medido el 30-ago-2026** invocando la herramienta
registrada contra 40 datasets por país, muestreando uno por desplazamiento del catálogo en
vez de por páginas enteras:

| País | Datasets muestreados | Devolvieron filas | Cobertura |
|---|---|---|---|
| México | 40 | 39 | 97,5% |
| Uruguay | 40 | 38 | 95,0% |
| Argentina | 40 | 26 | 65,0% |
| Chile | 40 | 15 | 37,5% |
| Panamá | 40 | 11 | 27,5% |
| **Los cinco** | **200** | **129** | **64,5%** |

Se reproduce con `uv run python -m opendata_latam_mcp.sweep --countries AR,CL,MX,PA,UY
--per-country 40 --seed 42`. La diferencia no es un defecto: el DataStore cubre una
fracción de cualquier catálogo y el resto se publica como archivo suelto. Panamá es el
caso más marcado — el catálogo más grande de aquí y la cobertura más baja, así que tamaño
y legibilidad no van juntos.

**No agrega, y eso es una medición y no una omisión.** `datastore_search_sql`, la acción
de CKAN que correría un `GROUP BY` en el portal, se probó contra seis portales nacionales
el 30-ago-2026 y responde solo en Uruguay; en todos los demás es HTTP 400. El mínimo, el
máximo, el promedio y el `GROUP BY` no se le pueden pedir al portal y pertenecen a una capa
local por encima de estas filas. Es exactamente por eso que el servidor dominicano tiene
una capa DuckDB — era la única opción, no una preferencia.

Importa porque casi todos estos portales publican el mismo dato de varias formas, y solo
algunas de ellas son una tabla consultable. Leer filas de verdad significa encadenar tres
vías —el DataStore de CKAN, luego un servicio ArcGIS REST, luego el archivo publicado— y
detenerse en la primera que devuelve filas. Ese trabajo existe, y vive en los dos paquetes
dedicados por país:

| | Profundidad | Qué puede hacer |
|---|---|---|
| [`dominican-open-data-mcp`](https://github.com/alcastaro/datos.gob.do-MCP-server) | Profunda | Descarga el archivo publicado, lo parsea, repara enlaces muertos y lo consulta con SQL vía DuckDB. Su portal **no tiene DataStore**, así que cada fila tiene que salir de un archivo. |
| `colombian-open-data-mcp` | Profunda | Tres vías encadenadas: DataStore de CKAN → servicio ArcGIS REST → archivo publicado. Cobertura medida: 100% nacional, 89,2% en Bogotá. |

Esos dos se **importarán** en este servidor en vez de reimplementarse, para que un arreglo
en el código compartido llegue a todos a la vez. Mientras tanto, la descripción honesta de
este es: te dice qué datasets existen en América Latina y dónde están. Decirlo en las
descripciones de las herramientas es deliberado — un servidor que promete una profundidad
que no tiene le cuesta al modelo un turno descubrirlo.

**El servidor no guarda nada.** Ni caché, ni espejo, ni copias de los datos de nadie.
Conservar estos datasets convertiría a quien lo opere en responsable del tratamiento bajo
la Ley 1581 de Colombia y sus equivalentes. Es una decisión tomada a propósito, no un
efecto secundario de no haber construido todavía una caché.

## Herramientas expuestas

15 tools en total: 11 de catálogo por país, 1 de lectura de filas por país, 2 cross-país, 1 catálogo.

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

→ `cross_country_stats()` → devuelve Panamá 5.667 / Chile 3.188 / Uruguay 2.702 / México 1.736 / Argentina 1.273 / República Dominicana 1.062.

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
- **Cross-country es `asyncio.gather`.** Fan-out en paralelo contra N portales, devuelve dict por país + summary. Latencia sub-3-segundos contra todos los portales. Un portal que falla devuelve su error dentro del resultado; no tumba a los demás.
- **System trust store para SSL.** Algunos portales LatAm (notablemente `datos.gob.mx`) shipean chains TLS incompletos que `certifi` no puede verificar. `truststore` inyecta el OS trust store, que `curl` ya usa, así httpx los acepta.
- **Truncado defensivo.** Descripciones largas truncadas a 300 chars en listados. Dumps cross-country con 6 países × 10 datasets × descripciones multi-KB volarían context windows sin esto.
- **FastMCP idiomático.** Args tipados con Pydantic; sin schema manual. Cada tool es una función decorada.
- **Logging solo stderr.** Requerido por spec MCP para servers stdio (stdout es el protocol stream).

### Stack

- [`mcp`](https://pypi.org/project/mcp/) (FastMCP) · [`httpx`](https://www.python-httpx.org/) · [`truststore`](https://pypi.org/project/truststore/) · [`duckdb`](https://duckdb.org/) (para layer analytics planeada v0.5) · [`openpyxl`](https://openpyxl.readthedocs.io/) · [`chardet`](https://chardet.readthedocs.io/) · [`odfpy`](https://github.com/eea/odfpy).

---

## Roadmap

- **v0.1** — 7 países CKAN (AR, CL, DO, EC, MX, PA, UY) · cross-country search + stats.
- **v0.2** — Colombia a través del paquete `colombian-open-data-mcp`: 5 portales en
  2 plataformas (Socrata a nivel nacional, CKAN para Bogotá, Cali, Valle del Cauca y
  Cartagena). Importado como biblioteca, no copiado, para que un arreglo en el código de
  seguridad compartido llegue a todos los servidores que lo usan.
- **v0.3** — Leer filas, empezando por el DataStore de CKAN. Es una capacidad de la
  familia CKAN y no de un país concreto, así que aterriza en `adapters/ckan/base.py` y
  levanta a Panamá, Chile, México y Uruguay de una sola vez.
- **v0.4** — Perú y Paraguay vía un adaptador DKAN. **Perú NO está «protegido por CloudWAF»** —
  esa afirmación anterior era falsa y la medición del 30-ago-2026 la desmintió. Perú corre
  DKAN sobre Drupal 7 y sirve un API de acciones de CKAN *parcial*: funcionan
  `package_list` (4.670 datasets), `package_show` y `group_list`, mientras que
  `package_search`, `organization_list`, `tag_list` y `resource_search` devuelven 404.
  No hay búsqueda del lado del servidor, así que cualquier búsqueda sobre Perú será del
  lado del cliente y así se declarará.
- **v0.4+** — Brasil (`dados.gov.br`, token Bearer por registro de desarrollador).
  Bolivia y Guatemala responden HTTP 403 a todo; **este proyecto no suplanta un navegador
  para sortear un WAF**, así que quedan sin soporte salvo que se abran.
- **v0.5** — Portar la capa analytics de `dominican-open-data-mcp` (cache DuckDB, `filter_resource`, `aggregate_resource`, `query_resource`) así el mismo escape hatch SQL funciona contra cualquier recurso de portal cacheado.
- **v0.6** — Analytics cross-country: `compare_indicators`, `find_equivalent_datasets`, alineación de series temporales entre países.

Ver [`Roadmap.md`](https://github.com/alcastaro/datos.gob.do-MCP-server/blob/main/Roadmap.md) en el repo RD MCP para el inventario completo de portales LatAm.

## Limitaciones conocidas

- Solo metadatos — ver la sección de alcance más arriba.
- Ecuador no responde; Colombia, Brasil, Perú, Paraguay y Bolivia aún no soportados.
- Queries cross-country son tan lentas como el portal más lento.
- La calidad de datos de cada portal es la que entrega el gobierno publicador; este MCP no normaliza schemas entre países (planeado para v0.6).

## Contribuciones

Pull requests bienvenidos. La forma más rápida de añadir valor: shipear un nuevo adapter de país. Portales CKAN son típicamente un archivo (~5 líneas, override URL). Portales no-CKAN necesitan un cliente nuevo implementando el `PortalAdapter` Protocol.

## Créditos

Construido por [@alcastaro](https://github.com/alcastaro). Inspirado en [`datagouv-mcp`](https://github.com/datagouv/datagouv-mcp) (Etalab, Francia) y [`dominican-open-data-mcp`](https://github.com/alcastaro/datos.gob.do-MCP-server) (el MCP single-country previo del mismo autor).

## Licencia

MIT para el código fuente. Datos accedidos a través de este MCP son publicados independientemente por cada gobierno bajo sus propios términos (típicamente ODbL o Creative Commons). Ver [LICENSE](LICENSE).
