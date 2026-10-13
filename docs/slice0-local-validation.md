# Slice 0 — contrato, verificación y límites

Candidato local desde `a1c226260019c0da40d45eff2d1fa5dd42b40ce4`, sin commit.
MCP permanece deshabilitado por defecto. Los datos de prueba y bindings sintéticos
se crean en bases desechables; no son altas ni permisos reales.

## Frontera de liberación

`POST /expedientes/{id}/release-evaluations` recibe document_version_id y bundle.
El servidor consulta la versión del expediente, lee sus bytes persistidos, verifica
el hash almacenado y extrae texto. response_text debe coincidir exactamente con
esa extracción; extracted_text aportado al subir el documento nunca es evidencia.
Se ejecutan autoridad y grounding con políticas e índices del servidor. Se persiste
GateExecution con actor, expediente, versión, bundle y su hash, bytes y su hash,
texto/método de extracción, hashes de políticas/índices, verdict, gates y evidencia.
Excepciones de resolvedores generan un resultado bloqueado.

`POST /expedientes/{id}/release-receipts` acepta exclusivamente:

```json
{"execution_id": "UUID de evaluación persistida", "bundle": {"mismo": "bundle íntegro"}}
```

verdict, gate_summary, actor, política, paths, hashes y demás campos declarados se
rechazan. Se comparan execution/evidence/receipt entre sí y contra documento,
actor y políticas actuales. Evidencia ausente, modificada, vencida o de otro actor,
expediente, versión o bundle no puede producir una aprobación. La vigencia por
defecto es 900 segundos. Un reintento equivalente devuelve el mismo recibo sin
repetir auditoría ni outbox. Gates fallidos pueden producir un recibo blocked;
ninguna de estas rutas admite bypass ni approved elegido por cliente.

La REST API mantiene el mecanismo API key existente que resuelve un AppUser local
reviewer/admin. API key no autentica MCP. Consola, interfaz y CLI liberan a través
de MCP con bearer individual, sin usar la API key compartida de la consola para
esta operación. Otras operaciones heredadas de la consola conservan su proxy actual.
No se implementa control granular por expediente: el alcance sigue siendo el rol
local existente, sin ACL ni concesión nueva de acceso persistente.

MCP expone whoami, evaluate_document_release y release_document. Solo acepta el
contexto autenticado del SDK, exige legalize:read y, para liberar, legalize:release
más rol local reviewer/admin. La identidad resulta del binding activo y único
(issuer, subject) a AppUser activo; no del email, argumentos o metadata. Cada
handler construye capabilities una vez con una consulta nueva. Stdio/in-memory
sin ese contexto rechazan los tres handlers protegidos.

## Clientes y sesión

La CLI `scripts/release_legal_response.py` es cliente del servidor MCP con el SDK
oficial. Requiere bundle, expediente y versión persistidos, endpoint /mcp y bearer
de una sesión ya existente en LEGALIZE_MX_SESSION_BEARER. No acepta token como
argumento CLI, actor, verdict, fixtures, políticas o destino de artefactos. Solo
emite APPROVED después del recibo persistido que corresponde a la evaluación.
El evaluator compartido legal_release_gates.py devuelve resultados PASS/FAIL;
no libera ni exporta un aprobado local. Panel --skip-release produce RELEASE_PENDING.

La consola transmite el bearer del navegador al MCP. La interfaz recibe la sesión
OAuth del host mediante legalize-auth-session/accessToken, en memoria; no crea
login/IdP, no vincula usuarios, no solicita credenciales ni persiste tokens. Mostrar
un evento de sesión no concede permisos: el servidor verifica el token y binding.
Evaluación muestra gates del servidor y confirmación consume su execution ID.
Cambiar sesión, expediente, versión o bundle invalida la evaluación. Si el contexto
cambia mientras se confirma, la UI refiere el recibo a la operación anterior y
no muestra una aprobación como resultado de la selección actual. Chromium probó
esta carrera demorando una respuesta real después del commit del servidor.

## Formatos soportados

TXT/MD UTF-8; PDF de texto simple y DOCX de párrafos/tablas simples. Extracción
lógica ligada a bytes, hash de texto y versión del extractor. No es certificación
visual ni OCR, ni garantiza orden visual/layout equivalente a todo texto extraído.

Límites: 16 MiB de bytes, 32 MiB de expansión, 2 millones de caracteres, 200 páginas.
PDF/DOCX se procesan en un worker con 512 MiB de memoria, 10 s de CPU y 12 s de
plazo. Se rechazan cifrado, archivos malformados/mal rotulados, imágenes/forms/
annotations, PDF ExtGState y operadores fuera del subconjunto de texto (incluye
rechazo de 3 Tr, colores, clipping y optional content), DOCX headers/footers/notas/
macros/revisiones/contenido externo/tablas anidadas/texto oculto, incluso en estilos.
Todos los XML/relationships del DOCX se analizan con defusedxml, prohibiendo DTD,
entidades y referencias externas. La geometría y fuentes PDF y el render DOCX no
se modelan exhaustivamente; se requiere otro contrato si se exige equivalencia
visual para liberar documentos generales. Las pruebas positivas son sintéticas.

## Operación y migración

Futura activación requiere configuración HTTPS explícita de issuer, JWKS y recurso
/mcp. Firma asimétrica de PyJWT/cryptography; algoritmo, iss/sub/aud/exp/nbf y scope
se validan. No se descubren endpoints desde claims/jku/x5u del token. JWKS usa
5 s timeout y caché de conjunto de claves de 60 s; kid nuevo refresca. Una clave
válida cacheada puede usarse durante esa ventana aunque JWKS esté caído. Bindings
inactivos/usuarios inactivos se rechazan en cada invocación. No hay endpoint de
provisionamiento ni vinculaciones por email. No se configuró un proveedor real.

Recibo, auditoría y outbox comparten una transacción. execution_id único evita
recibos duplicados; un evento único por recibo exporta
storage_root/releases/outbox/{event_id}.json, sin destinos ni servicios externos.
El worker valida todos los bindings comprometidos antes de escribir; usa archivo
atómico y fsync de archivo/directorio, también al recuperar un efecto ya escrito.
Después de crash/commit fallido reintenta idempotentemente el mismo evento. Exporta
la decisión comprometida, sin reevaluar políticas nuevas en una entrega posterior.
No promete exactly-once en servicios externos. DB y filesystem son frontera de
confianza: hashes no son firmas contra un administrador que reescriba todo.

La revisión 0003 conserva recibos históricos con execution_id nulo, sin tratarlos
como evidencia nueva. Normaliza los enums SQLite y los restaura al downgrade para
que main pueda leerlos. PostgreSQL usa valores de enum iguales al ORM y creación
única de tipos en la cadena histórica. Se verificó upgrade 0001→0002→0003,
alembic check, lectura del recibo anterior y downgrade vacío en PostgreSQL temporal;
y upgrade/check/downgrade desde esquema main archivado en SQLite. Downgrade con
evidencia/bindings/outbox se bloquea para evitar pérdida silenciosa. create_all
no actualiza tablas antiguas; se necesita la migración antes de habilitar rutas.

## Reproducción local

Instalar Python 3.12 y el editable `python -m pip install -e '.[dev]'` en una venv
nueva del checkout. Ejecutar `python -m pytest -q`. La suite incluye HTTPS/JWKS
sintéticos y clientes reales; Chromium requiere Node, Playwright y /usr/bin/chromium.
El fixture crea CA/claves efímeras de test y servidores loopback; no usa tokens de
proveedores reales. El test PostgreSQL se omite salvo que se aporte
LEGALIZE_MX_TEST_DATABASE_URL para una base desechable `legalize_slice0_test` en
127.0.0.1/localhost sin password. Cada test crea y elimina su propio schema UUID;
no apuntar ese fixture a producción. Ver matrix/logs del paquete para comandos y
resultados efectivos, incluidos fallos históricos y correcciones posteriores.

## Límites restantes

Trabajo local histórico/Surface no recuperado; falta comparación con ese diff.
Pruebas de contratos sintéticos no certifican IdP/proxy/configuración productivos;
la aceptación de despliegue requiere otro alcance autorizado. DOF y conectores
licenciados sin un adapter de texto canónico fallan cerrados; metadata sola no
prueba quote/locator. La URL live SCJN es la consultada por el servidor, jamás un
fallback del cliente. Los gates actuales no detectan exhaustivamente afirmaciones
omitidas de citations/claims. APPROVED significa PASS de estas políticas y gates,
no corrección jurídica ni cobertura completa de afirmaciones. Esa propiedad y
el contrato visual general siguen pendientes de especificar; no se alteró la
política JSON canónica para aparentar haberlos resuelto. Slice 0 no se declara completo.
