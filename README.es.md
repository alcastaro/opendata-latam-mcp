<!-- mcp-name: io.github.alcastaro/opendata-latam-mcp -->

**[English](README.md) · [Español](README.es.md)**

---

# opendata-latam-mcp

**Servidor [Model Context Protocol](https://modelcontextprotocol.io) unificado que expone los datos abiertos del gobierno de cada país latinoamericano soportado a través de una sola interfaz.**

Una instalación, seis portales vivos, **15.628 datasets públicos** de Argentina, Chile, México, Panamá, República Dominicana y Uruguay — buscables y consultables cruzando países desde cualquier asistente de IA compatible con MCP (Claude Desktop, Claude Code, Cursor, Gemini CLI, ChatGPT Desktop).

> **Léase esto antes que nada:** catorce de las quince herramientas son de **nivel catálogo** — encuentran datasets y los describen. Solo `read_resource_rows` devuelve filas, y solo donde el portal construyó una tabla DataStore de CKAN para ese recurso (medido: 64,5% de los datasets muestreados en cinco portales). Sin descarga de archivos, sin parseo. Ver [Alcance: qué hace y qué no hace](#alcance-qué-hace-y-qué-no-hace).

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

### Por qué Colombia no está en la tabla

Es la pregunta que esta tabla invita a hacer, porque Colombia tiene la plataforma de datos
abiertos más rica de la región y ya existe un servidor MCP dedicado a ella. Tres razones,
ordenadas por lo que cuesta resolverlas:

**Colombia no es un país más, es otra plataforma.** Todos los países de arriba corren
CKAN — el mismo software de catálogo con el mismo API — así que comparten un único cliente
y añadir uno cuesta un archivo de cinco líneas con una URL. Colombia a nivel nacional corre
**Socrata**, un producto distinto con su propio lenguaje de consulta (SoQL), y además tiene
cuatro portales *municipales* que sí son CKAN. Eso exige una familia de adaptadores nueva,
no un descriptor. El directorio `adapters/socrata/` existe en este repositorio y está vacío
a propósito, esperándola.

**La decisión es importar ese trabajo, no reescribirlo.**
[`colombian-open-data-mcp`](https://github.com/alcastaro/colombian-open-data-mcp) ya
implementa Socrata, la lectura de filas por tres vías encadenadas y los portales municipales
CKAN, medido contra los portales vivos. Reimplementarlo aquí duplicaría algunos miles de
líneas y compraría divergencia — y eso no es hipotético: el módulo compartido de protección
SSRF ya existe en tres copias que se separaron entre sí, y el 12-sep-2026 una revisión
independiente de la colombiana encontró dos huecos que la copia de este repositorio también
tenía. Una sola implementación, importada por cada servidor, es justamente el objetivo.

**Lo que hoy bloquea la importación es la publicación, no el código.** Un paquete solo se
puede importar si se puede instalar, y una dependencia por ruta local o por git rompe las
instalaciones con `uvx`, que es como se instalan estos servidores. `colombian-open-data-mcp`
todavía no está en PyPI (verificado el 13-sep-2026). Eso fuerza el orden: **primero el
paquete colombiano, después este.**

Mientras tanto el usuario no pierde nada: el servidor colombiano se instala por separado y
funciona hoy. Lo que falta es la *unificación* — tener a Colombia dentro del mismo
`cross_country_search` que barre los demás portales en paralelo. Eso llega en v0.3.

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

Cada tool acepta un parámetro `country`: `AR`, `CL`, `DO`, `EC`, `MX`, `PA`, `UY` (`EC` está configurado pero no responde — ver arriba). La lista que ve el modelo se genera desde el registro, así que no puede desviarse de esta.

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
| `read_resource_rows` | Las filas de un recurso, a través del DataStore de CKAN del portal — paginadas, filtrables por texto libre, celdas truncadas. Donde el portal no construyó tabla devuelve un error que lo dice y qué intentar en su lugar. |

### Cross-country (el value-add único)

| Tool | Qué hace |
|---|---|
| `cross_country_search` | Busca el mismo término en todos (o seleccionados) los portales de LatAm en paralelo. Devuelve breakdown por país + total grand. |
| `cross_country_stats` | Corre `get_site_stats` contra todos los países soportados en paralelo. Health check rápido + tamaños comparativos. |

---

## Instalación y configuración

### Opción A — Vía `uvx` desde PyPI

Una vez que el paquete esté publicado en PyPI (todavía no — hasta entonces el repositorio es la fuente de verdad):

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
├── server.py              Entry MCPServer (SDK v2); las 15 tools registradas acá
├── errors.py              El sobre {"error", "hint"} que devuelve cada tool
├── netguard.py            Guardia SSRF en cada salto (copia interina del módulo compartido)
├── sweep.py               Arnés de cobertura — ninguna cifra sale sin él
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
    │   ├── panama.py
    │   └── uruguay.py
    └── socrata/           (v0.3 — Colombia, importado)
```

### Decisiones de diseño

- **Adapter pattern como costura.** Cada portal expone el mismo `PortalAdapter` Protocol. Añadir un país = subclasear + un override URL. Los portales CKAN comparten la implementación entera; Socrata y custom se enchufan al mismo registry.
- **Código país como clave primaria.** Cada herramienta requiere `country` (ISO alpha-2). El modelo siempre sabe qué portal está consultando.
- **Devolver, nunca lanzar — toda herramienta, todo fallo.** Una herramienta que falla
  devuelve `{"error": ..., "hint": ...}` como resultado ordinario: `error` conserva el
  mensaje del propio portal y `hint` dice qué intentar a continuación. Un código de país
  no soportado indica llamar a `list_supported_countries`; un portal que responde 403
  aclara que el rechazo es política y no una petición mal formada, así que reintentar no
  sirve, y `cross_country_search` lo reporta por país sin tumbar la llamada entera.

  Esto está medido, no es aspiracional. Antes de existir, una sesión de cliente real
  llamando a `search_datasets` con un país inválido recibía exactamente `Error executing
  tool search_datasets` y nada más — el SDK descarta el mensaje subyacente. Un modelo con
  eso no distingue un argumento equivocado de un portal caído, así que reintenta a ciegas.
- **Toda herramienta devuelve un objeto, nunca una lista suelta.** Eso es lo que hace
  posible el sobre: el SDK deriva un esquema de salida del tipo de retorno y rechaza una
  forma distinta, así que una herramienta que devolviera una lista no podría devolver un
  sobre de error. Las listas viven bajo una clave con nombre (`groups`, `tags`,
  `suggestions`), lo que además le da al modelo el contexto del portal que una lista
  suelta nunca llevaba.
- **La salud del portal es legible por máquina.** `list_supported_countries` reporta un
  `status` por portal, para que el modelo pueda rodear uno caído en vez de gastar un turno
  descubriéndolo.
- **Cross-country es `asyncio.gather`.** Fan-out en paralelo contra N portales, devuelve dict por país + summary. Latencia sub-3-segundos contra todos los portales. Un portal que falla devuelve su error dentro del resultado; no tumba a los demás.
- **System trust store para SSL.** Algunos portales LatAm (notablemente `datos.gob.mx`) shipean chains TLS incompletos que `certifi` no puede verificar. `truststore` inyecta el OS trust store, que `curl` ya usa, así httpx los acepta.
- **Truncado defensivo.** Descripciones largas truncadas a 300 chars en listados. Dumps cross-country con 6 países × 10 datasets × descripciones multi-KB volarían context windows sin esto.
- **MCP SDK v2 idiomático (`MCPServer`).** Args tipados con Pydantic y un esquema de salida de objeto en cada tool; sin schema manual. Cada tool es una función decorada, envuelta en el sobre de errores.
- **Logging solo stderr.** Requerido por spec MCP para servers stdio (stdout es el protocol stream).

### Stack

- [`mcp`](https://pypi.org/project/mcp/) (SDK v2, `>=2.1,<3`) · [`httpx`](https://www.python-httpx.org/) · [`truststore`](https://pypi.org/project/truststore/). Tres dependencias de runtime, a propósito: el stack de parseo de archivos y DuckDB llega con los paquetes de país importados en v0.5, no antes.

---

## Roadmap

- **v0.1** (publicada 2026-05) — 6 países CKAN · cross-country search + stats.
- **v0.2** (esta versión) — Panamá · MCP SDK v2 · lectura de filas a través del DataStore
  de CKAN, medida y no supuesta (tabla arriba) · un `{"error", "hint"}` accionable desde
  cada herramienta en vez de un error de protocolo opaco · guardia SSRF en cada salto de
  redirección.
- **v0.3** — Colombia a través del paquete `colombian-open-data-mcp`: 5 portales en
  2 plataformas (Socrata a nivel nacional, CKAN para Bogotá, Cali, Valle del Cauca y
  Cartagena). Importado como biblioteca, no copiado, para que un arreglo en el código de
  seguridad compartido llegue a todos los servidores que lo usan. Los reintentos llegan
  por la misma vía.
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
- **v0.5** — Agregación sobre recursos completos, calculada localmente en DuckDB con el motor
  importado de `dominican-open-data-mcp`. Local porque no hay otra: `datastore_search_sql`
  responde solo en Uruguay, así que ningún portal de aquí puede correr un `GROUP BY` por
  nosotros. Sigue sin caché en disco — las filas se retienen para la llamada y se descartan.
- **v0.6** — Analytics cross-country: `compare_indicators`, `find_equivalent_datasets`, alineación de series temporales entre países.

Ver [`Roadmap.md`](https://github.com/alcastaro/datos.gob.do-MCP-server/blob/main/Roadmap.md) en el repo RD MCP para el inventario completo de portales LatAm.

## Limitaciones conocidas

- Las filas llegan solo por el DataStore de CKAN, que cubre una fracción de cada catálogo
  (64,5% de los datasets muestreados en cinco portales; ninguno en República Dominicana).
  Sin descarga ni parseo de archivos todavía — ver la sección de alcance más arriba.
- Ecuador no responde. Colombia se sirve desde su propio paquete y no desde aquí — ver [Por qué Colombia no está en la tabla](#por-qué-colombia-no-está-en-la-tabla). Brasil, Perú, Paraguay y Bolivia aún no soportados.
- Queries cross-country son tan lentas como el portal más lento.
- La calidad de datos de cada portal es la que entrega el gobierno publicador; este MCP no normaliza schemas entre países (planeado para v0.6).

## Contribuciones

Pull requests bienvenidos. La forma más rápida de añadir valor: shipear un nuevo adapter de país. Portales CKAN son típicamente un archivo (~5 líneas, override URL). Portales no-CKAN necesitan un cliente nuevo implementando el `PortalAdapter` Protocol.

## Créditos

Construido por [@alcastaro](https://github.com/alcastaro). Inspirado en [`datagouv-mcp`](https://github.com/datagouv/datagouv-mcp) (Etalab, Francia) y [`dominican-open-data-mcp`](https://github.com/alcastaro/datos.gob.do-MCP-server) (el MCP single-country previo del mismo autor).

## Licencia

MIT para el código fuente. Datos accedidos a través de este MCP son publicados independientemente por cada gobierno bajo sus propios términos (típicamente ODbL o Creative Commons). Ver [LICENSE](LICENSE).
