# Slice 0 — candidato local revisado, sin commit

Estado: **NOT_READY_FOR_COMMIT**; Slice 0 no se declara completo.
Fecha: 2026-10-13. Base y HEAD: `a1c226260019c0da40d45eff2d1fa5dd42b40ce4`.
Checkout nuevo y aislado: `/workspace/legalize-slice0-candidate`, detached HEAD.
El candidato demuestra contratos de autenticación/liberación/persistencia y clientes;
conserva límites de recuperación histórica, semántica y equivalencia visual.

## Resultado actual

| Frontera | Implementación | Evidencia efectiva |
| --- | --- | --- |
| MCP | SDK oficial 2.3.0 Streamable HTTP; PyJWT/JWKS; issuer/audience/exp/nbf/sub, firma/algoritmo y scopes; HTTPS explícito, deshabilitado por defecto | JWT válidos/claims inválidos/firma incorrecta/HS256/none/JWKS fallo y rotación; HTTPS real con JWKS sintético, montaje/lifespan |
| Actor | Binding persistente único issuer/subject a AppUser activo, sin autoalta/email | Binding ausente/inactivo, usuario inactivo, issuer distinto, scopes/roles, dos actores consecutivos; metadata no establece identidad |
| Invocación | SDK authenticated context, capabilities una vez por handler | Tres handlers protegidos rechazan stdio/in-memory; conteo por invocación, actor2 no consume ejecución actor1 |
| Evidencia | Gates del servidor; hash de bundle/bytes/políticas/índices, actor/expediente/versión/verdict/execution ID y extracción vinculados | Negativos por falta/alteración, rehash inconsistente, versión/actor/hash/verdict/execution equivocados, gates ausentes, caducidad/política cambiada |
| Recibo | API elimina verdict/gate_summary declarados; consume ejecución persistida para el mismo bundle | approved directo y parámetros históricos rechazados; retorno equivalente idempotente; REST conserva autenticación API key local reviewer/admin, MCP solo bearer |
| Autoridad | Identidad/título/URL/quote/locator canónicos estrictos; fuente SCJN del endpoint consultado; metadata/DOF/proveedores sin texto no bastan | Reproducciones de legislación inventada, identidad contradictoria y URL live del cliente pasan a blocked; fixtures positivos son explícitamente sintéticos |
| Formatos | TXT/MD, PDF/DOCX simples desde bytes persistidos; worker con límites; ignores extracted_text cliente | Positivos de bytes/texto/hash/método y tamper; malformados/cifrados, 3Tr/color/optional content/gs, DOCX estilo oculto y contenido no soportado rechazados |
| Transacción/outbox | Recibo+audit+evento juntos; ejecución y evento únicos; efecto local por UUID atómico/fsync | Rollback, reintentos, concurrencia, crash después de efecto antes de commit, recuperación y filas/payload alterados; contratos SQLite y PostgreSQL |
| Clientes | CLI y consola consumen MCP con bearer individual; panel skip-release es RELEASE_PENDING; interfaz muestra gates y confirma ID servidor | CLI real y flags históricos rechazados; consola 401/422 y retry; Chromium actor correcto, invalidación y carrera de confirmación con respuesta real demorada |
| Migraciones | Cadena PostgreSQL corregida para enum types/valores e índices; 0003 no aprovisiona acceso; legacy execution_id nulo | PostgreSQL 0001→0002→0003/check/recibo previo/downgrade vacío; SQLite esquema main/upgrade/check/downgrade y lectura posterior con código main archivado |

## Pruebas y revisión

Suite completa sobre el candidato final: **114 passed, 1 failed, 1 skipped en 42.30 s**.
El skip corresponde a la prueba PostgreSQL cuando no se proporciona su fixture;
la cadena PostgreSQL se ejecutó y aprobó separadamente. El único fallo es calendario:
`test_calendar_agenda_aggregates_deadlines_and_audiencias`, línea 151. El mismo
fallo se reprodujo en un archivo íntegro del main exacto, con la misma venv y fecha,
en `baseline-calendar-equivalent.log`: usa eventos de abril y ventana desde octubre.
No se modificó calendario ni ese test. No se presenta una suite totalmente verde.

| Ejecución | Resultado | Log en paquete |
| --- | --- | --- |
| Candidato final completo | 114 passed, 1 failed (baseline), 1 skipped | pytest-final-current.log |
| Correcciones finales autor: formatos/evidencia/SQLite/gates | 49 passed, 17.12 s | round3-corrections-final.log |
| PostgreSQL autor: auth/HTTP/CLI/interfaz/cadena | 39 passed, 26.43 s | postgres-auth-http-round2.log |
| PostgreSQL cadena individual posterior a corrección | 1 passed, 2.85 s | postgres-migration-round2.log |
| Revisor independiente: contratos SQLite/HTTPS/JWKS/CLI/Chromium | 76 passed, 36.65 s | independent-review-round2-contracts.log |
| Revisor independiente: contratos y cadena PostgreSQL | 76 passed, 43.56 s | independent-review-round2-postgres.log |
| PostgreSQL focal final: nuevas correcciones de fuentes/formatos | 9 passed, 4.55 s | postgres-final-corrections.log |
| Revisor: cierres fuente/formatos/rollback/carrera UI | 10 passed, 10.53 s | independent-review-final-changes.log |

Las ejecuciones anteriores fallidas se conservan aparte: ronda inicial 83 passed y
calendario; intento inicial PostgreSQL con tipo enum duplicado y después drift/
interpolación; batch con cuatro negativos PDF fallidos por bool(ContentStream)
y 49 passed. Los resultados posteriores demuestran las correcciones. No se suman
batches solapados ni se presentan reproducciones de defectos como aprobación final.

Revisión separada por `/root/independent_review`: ronda 1 encontró cuatro defectos;
ronda 2 confirmó esos cierres y encontró fuente live autodeclarada, rollback SQLite,
DOCX oculto, PDF invisible y carrera UI. Nueve hallazgos corregidos, sin otro defecto
reproducible en los cambios finales revisados. Informes originales y reproducciones
se incluyen sin sobrescribir; el informe final se lee junto con ellos.

Compileall, sintaxis JS (app y browser), pip check y git diff --check aprobados.
Bandit 1.9.4, seis módulos nuevos: 0 high, 0 medium, **3 low** (B404 import de
subprocess en dos módulos y B603 worker sin shell). Se revisaron: comando fijo
sys.executable/módulo local, argumento suffix, bytes por stdin, sin shell, con timeout
CPU/memoria. No se suprimieron ni se afirmó cero hallazgos. El warning XML medium
del análisis intermedio quedó eliminado al usar defusedxml con restricciones.
Bandit es herramienta local de revisión, no dependencia productiva.

Versiones instaladas: Python 3.12.14; MCP 2.3.0; PyJWT 2.15.1; httpx2 2.13.1;
pypdf 6.20.1; python-docx 1.2.0; defusedxml 0.7.1; cryptography 50.0.2;
FastAPI 0.143.0; SQLAlchemy 2.1.4; Alembic 1.20.0. Snapshot completo en paquete.
El SDK y documentos oficiales actuales respaldan las firmas usadas; no se asumió
la versión citada históricamente. Las dependencias productivas nuevas son visibles
en pyproject.toml y solo se instalaron en la venv del candidato.

## Fuentes y límites conservados

GitHub permitió clonar y leer main/referencias/PR/issues. No apareció trabajo remoto
Slice 0. No se recuperó `/root/legalize-mx` de otro servidor ni Surface. Personal
Context devolvió «Personal context is unavailable for this conversation»; no se pudo
recuperar el hilo/diff histórico. El reporte de septiembre aportado por Francisco
se conserva como contexto, sin atribuirle implementación nueva ni inventar comparación.
No hay AGENTS.md/.agents/skills en main; se leyeron .claude/CLAUDE.md y la copia
histórica context/root-AGENTS.md. Ninguna exige aprobar historia/dependencias para
este diff autorizado; no se alteró política JSON canónica ni se amplió acceso real.

Se restauró el mismo entorno tras `exec-server transport closed`; una sesión vieja
no pudo recuperarse. No se cambió autenticación ni se eludió una denegación. El
PostgreSQL oficial 17 temporal usó red propia, puerto solo 127.0.0.1, base y schemas
UUID desechables sin password. Recursos exactos se retiran al cerrar y se entrega
log de limpieza. No se tocó PostgreSQL/base/contenedor productivo ni otros repos.

Pendientes para aceptar todo Slice 0:

1. Reconciliar el diff histórico si se recupera. No bloquea demostrar estos contratos,
   pero falta comparación de alcance y decisiones anteriores.
2. Definir si se exige cobertura completa de afirmaciones: el servidor no garantiza
   que citations/claims enumeren todo el texto. approved es PASS de políticas actuales,
   no corrección jurídica. No se cambia política canónica para ocultar este límite.
3. Definir contrato visual si se exige PDF/DOCX general: extracción lógica ligada a
   bytes con subconjunto limitado, sin garantía de equivalencia visual/layout/render.
   Geometría, fuentes, escala y orden visual no están certificados exhaustivamente.
4. Adapter de texto canónico para DOF/licenciados si su disponibilidad debe soportarse;
   hoy esas fuentes fallan cerradas cuando no hay evidencia local suficiente.
5. Aceptación de despliegue/IdP/proxy/TLS/alta-revocación real y, si se incluye en el
   alcance, ACL por expediente. No están autorizados ni se necesitan para validar
   contratos sintéticos. La sesión UI requiere integración con el host real; no se
   creó proveedor de identidad o flujo de login nuevo.
6. Estabilizar el test de calendario heredado si se exige suite totalmente verde.

No hubo staging, commit, push, PR, merge, despliegue, credenciales de proveedor,
permisos reales, bindings reales, cambios productivos ni modificación de otro repo.
El paquete incluye diff aplicable a main, copia íntegra de archivos cambiados,
manifiesto/hash, logs, revisiones y entrega inicial conservada. Ver
[especificación](slice0-candidate-spec.md) y [contrato](slice0-local-validation.md).
