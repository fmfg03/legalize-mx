# Slice 0: candidato local, 2026-10-13

Estado inicial: main `a1c226260019c0da40d45eff2d1fa5dd42b40ce4`.
Este documento especifica el candidato autorizado, no certifica Slice 0 completo.

## Fuentes y límites

- Se clonó GitHub en un checkout nuevo y separado. Main sigue en el SHA indicado.
- No se recuperó el checkout histórico `/root/legalize-mx` de otro servidor ni sus diffs.
  La Surface está desconectada. Personal Context devolvió «Personal context is
  unavailable for this conversation». El hilo referido no se pudo leer por ese medio.
- No existen `AGENTS.md` ni `.agents/skills` en este commit; se leyeron
  `context/root-AGENTS.md` y `.claude/CLAUDE.md`. La copia de instrucciones de `/root`
  es histórica y tiene un alcance de ruta distinto.
- No hay rama/PR visible de Slice 0: Git anuncia main, imgbot y PR 1 (imágenes).
  La búsqueda de issues de Slice 0 no encontró resultados. Esto no demuestra que
  no existan cambios locales fuera de las fuentes accesibles.
- El reporte del 19 de septiembre aportado por Francisco dice configuración OAuth
  solamente y NOT_READY_FOR_COMMIT; no se atribuye a ese trabajo el código nuevo.
- No se modifica otro repo, autenticación del entorno, política JSON canónica,
  configuración productiva, credencial, binding real ni proveedor de identidad.

## Contrato de implementación

1. MCP es un resource server OAuth separado del proveedor de identidad. Deshabilitado
   por defecto. Si se habilita, exige issuer, JWKS y URL HTTPS del recurso explícitos.
   Se usa el SDK oficial 2.3.0 y PyJWT 2.15.1 con su implementación criptográfica.
   No se acepta API key en MCP. Se verifica firma, algoritmo permitido, issuer,
   audience, exp, nbf y subject; scopes y rol local restringen cada operación.
2. Un binding persistente y único `(issuer, subject)` apunta a un AppUser activo.
   No se vincula por email ni se autoaprovisionan usuarios. No se implementa un
   endpoint para ampliar acceso persistente en este candidato.
3. Los handlers protegidos usan exclusivamente `get_access_token()` del SDK y
   rechazan llamadas stdio/in-memory sin ese contexto. Construyen capabilities
   una vez por invocación con una nueva consulta de binding/usuario. Argumentos
   y metadata del protocolo nunca establecen actor ni permisos.
4. La evaluación recibe un bundle y una versión del documento. Comprueba que el
   texto del bundle corresponde al contenido persistido de esa versión y ejecuta
   autoridad y grounding con políticas del servidor, sin fixtures elegidos por
   el cliente. Persiste execution ID, actor, expediente, versión, hash de bundle,
   hash de contenido y de políticas, verdict y evidencia. Excepciones bloquean.
5. La liberación recibe únicamente execution ID y el mismo bundle. Rechaza
   evidencia ausente o alterada, cambio de actor/versión/bundle/políticas o intento
   de elegir verdict/gate_summary. El recibo obtiene el verdict de la evidencia,
   nunca de la entrada. No admite BYPASS para versiones de documentos.
6. Recibo, auditoría y outbox se persisten juntos. Un execution ID solo genera un
   recibo. Reintentos equivalentes retornan el recibo existente; divergentes fallan.
   El outbox exporta un archivo por evento, mediante escritura atómica e idempotente,
   sin enviar nada a servicios externos. Recupera pendiente tras fallo/crash.

## Fases y verificación

- Primero: tests de JWT/JWKS, claims, scopes, binding, usuarios inactivos, dos
  actores consecutivos, HTTP y rechazo de transportes sin contexto.
- Después: gates reales y pruebas negativas de evidencia/binding de liberación,
  idempotencia, rollback y recuperación de outbox.
- Finalmente: suite existente, migración local desechable, revisión adversarial
  separada del diff, informe con resultados y pendientes. Sin commit.

## Fuentes oficiales consultadas

- [SDK: autorización](https://py.sdk.modelcontextprotocol.io/run/authorization/)
- [SDK: integración ASGI](https://py.sdk.modelcontextprotocol.io/run/asgi/)
- [SDK: migración v2](https://py.sdk.modelcontextprotocol.io/migration/)
- [MCP: autorización](https://modelcontextprotocol.io/specification/2025-11-25/basic/authorization)
- [PyJWT 2.15.1: API](https://pyjwt.readthedocs.io/en/latest/api.html)

Las dependencias productivas propuestas se harán visibles en pyproject.toml; solo
se instalan en `.venv` de este candidato. No se encontró regla local que requiera
aprobar una historia o dependencias antes de preparar este diff. La autorización
de implementación local no autoriza activar el servidor o dar acceso a usuarios.

## Ampliación local autorizada y revisada

CLI y consola son clientes MCP; interfaz muestra gates y confirma execution ID
con bearer de sesión del host. Panel skip-release no libera. PDF/DOCX simples se
extraen de bytes persistidos en worker limitado; se vinculan método y hash de texto
sin afirmar equivalencia visual general. DOF/proveedores sin texto canónico se
cierran; fuente SCJN deriva del endpoint consultado por servidor. Migración/cadena
histórica y contratos se probaron con PostgreSQL temporal y rollback SQLite leído
por main. Revisión independiente en rondas 1/2 y cierre final, con reportes y logs
fuera del repo incluidos en la entrega. Los nueve hallazgos reportados se corrigieron.

Fuentes adicionales: [pypdf oficial](https://pypdf.readthedocs.io/en/stable/),
[python-docx 1.2.0](https://python-docx.readthedocs.io/en/latest/),
[defusedxml oficial](https://github.com/tiran/defusedxml/blob/main/README.txt).
Pins productivos finales: MCP 2.3.0, PyJWT 2.15.1, httpx2 2.13.1, pypdf 6.20.1,
python-docx 1.2.0 y defusedxml 0.7.1; otros requisitos existentes conservan sus rangos.
La documentación instalada del SDK y sus firmas reales respaldan la integración;
no se asumió una versión histórica. Ver reporte y contrato final para la matriz de
pruebas y límites semánticos, visuales, históricos y de despliegue conservados.
