# Security Policy

**[English](#reporting-a-vulnerability) · [Español](#reportar-una-vulnerabilidad)**

---

## Reporting a vulnerability

**Please do not open a public issue for a security problem.** A public issue tells everyone
about the flaw before a fix exists, including the people who would use it.

Report it privately, either way:

- **GitHub Security Advisories** — the *Security* tab of this repository, *Report a
  vulnerability*. This is preferred: it gives us a private thread and a CVE if one is warranted.
- **Email** — `ai@olds2030.org`, with `opendata-latam-mcp` in the subject.

**What to expect.** This is maintained by one person as a side initiative, so the honest
commitment is an acknowledgement within **5 business days** and an assessment within **15**.
If a fix is warranted it ships in the next release, and you are credited unless you ask not
to be. If a report turns out not to be a vulnerability, you get the reasoning, not silence.

## What is in scope

This server reads public government open-data catalogues over HTTPS. It **holds no
credentials, writes nothing anywhere, and stores no data** — no cache, no mirror, no copies
of anyone's datasets. That shapes what a vulnerability here can look like:

- **SSRF and redirect handling.** No tool accepts a URL; every address is built from a
  portal's own configured base, and `netguard.py` validates every hop against
  `ipaddress.is_global` plus multicast and reserved ranges. A way around either of those is
  in scope and is the report we most want.
- **Identifier validation.** Resource identifiers go into a request path and are validated
  against a strict pattern. A bypass is in scope.
- **Query injection** into a portal's Solr or DataStore layer through a tool argument.
- **Supply chain** — the published artifacts, the dependency set, or anything in the build
  that would reach a user's machine.
- **Resource exhaustion** of the host process through a crafted portal response.

A **known and documented limitation**, which is not a finding: a DNS rebinding window
remains between our resolution and the HTTP client's. Closing it needs a pinned-address
transport. It is described in `netguard.py`.

## What is out of scope

- **The government portals themselves.** Their security is not ours to audit and not ours
  to authorize. If you find a flaw in a national open-data portal, report it to that
  government's own channel, not here.
- **Testing against the live portals.** Please do not run scans, fuzzers or load against
  `datos.gob.ar`, `datos.gob.cl`, `datos.gob.do`, `datos.gob.mx`, `datosabiertos.gob.pa`,
  `catalogodatos.gub.uy` or any other portal as part of research on this project. They are
  public services paid for by the countries they serve. Reproduce findings against a local
  fixture; the test suite shows how.
- Missing hardening that is already documented as a deliberate decision, unless you can show
  it is exploitable.

---

## Reportar una vulnerabilidad

**Por favor no abras un *issue* público por un problema de seguridad.** Un *issue* público
le cuenta la falla a todo el mundo antes de que exista el arreglo, incluida la gente que la
usaría.

Repórtalo en privado, por cualquiera de las dos vías:

- **GitHub Security Advisories** — pestaña *Security* de este repositorio, *Report a
  vulnerability*. Es la vía preferida: da un hilo privado y un CVE si corresponde.
- **Correo** — `ai@olds2030.org`, con `opendata-latam-mcp` en el asunto.

**Qué esperar.** Esto lo mantiene una sola persona como iniciativa paralela, así que el
compromiso honesto es acuse de recibo en **5 días hábiles** y evaluación en **15**. Si
corresponde un arreglo, sale en la siguiente versión, y se te da crédito salvo que pidas lo
contrario. Si el reporte resulta no ser una vulnerabilidad, recibes el razonamiento, no
silencio.

## Qué está en alcance

Este servidor lee catálogos públicos de datos abiertos de gobierno por HTTPS. **No guarda
credenciales, no escribe en ningún lado y no almacena datos** — sin caché, sin espejo, sin
copias de los datasets de nadie. Eso define cómo puede verse una vulnerabilidad aquí:

- **SSRF y manejo de redirecciones.** Ninguna herramienta acepta una URL; toda dirección se
  construye desde la base configurada del propio portal, y `netguard.py` valida cada salto
  contra `ipaddress.is_global` más los rangos multicast y reservados. Una forma de esquivar
  cualquiera de los dos está en alcance y es el reporte que más nos interesa.
- **Validación de identificadores.** Los identificadores de recurso entran en la ruta de una
  petición y se validan contra un patrón estricto. Un *bypass* está en alcance.
- **Inyección de consultas** en la capa Solr o DataStore de un portal a través del argumento
  de una herramienta.
- **Cadena de suministro** — los artefactos publicados, el conjunto de dependencias, o
  cualquier cosa del *build* que llegue a la máquina de quien lo instale.
- **Agotamiento de recursos** del proceso anfitrión mediante una respuesta de portal
  manipulada.

Una **limitación conocida y documentada**, que no es un hallazgo: queda una ventana de *DNS
rebinding* entre nuestra resolución y la del cliente HTTP. Cerrarla exige un transporte con
dirección fijada. Está descrita en `netguard.py`.

## Qué está fuera de alcance

- **Los portales de gobierno en sí.** Su seguridad no nos toca auditarla ni tenemos
  autorización para hacerlo. Si encuentras una falla en un portal nacional de datos
  abiertos, repórtala al canal de ese gobierno, no aquí.
- **Probar contra los portales vivos.** Por favor no corras escaneos, *fuzzers* ni carga
  contra `datos.gob.ar`, `datos.gob.cl`, `datos.gob.do`, `datos.gob.mx`,
  `datosabiertos.gob.pa`, `catalogodatos.gub.uy` ni ningún otro portal como parte de una
  investigación sobre este proyecto. Son servicios públicos pagados por los países a los que
  sirven. Reproduce los hallazgos contra un *fixture* local; la suite de pruebas muestra cómo.
- Endurecimientos ausentes que ya están documentados como decisión deliberada, salvo que
  puedas demostrar que son explotables.
