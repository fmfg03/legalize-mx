# Slice 0 — checkpoint de publicación, 2026-10-13

Francisco autorizó commit, publicación de rama, PR y merge («Autorizo todo hasta
merge», 2026-10-13 02:59:25 UTC). No autoriza despliegue, infraestructura, credenciales
ni permisos. MCP sigue deshabilitado por defecto. Las verificaciones productivas
son un alcance posterior; no se han hecho altas ni bindings reales.

El reporte/spec/plan del candidato conservan el estado histórico anterior a esa
autorización. NOT_READY_FOR_COMMIT en ese reporte agrupó límites y ausencia de
autorización; no identifica un defecto funcional del candidato que siga abierto.
La revisión independiente cerró nueve hallazgos. No se declara todo Slice 0 completo.

## Alcance y resultados conservados

Autenticación MCP fail-closed, binding issuer/subject persistente, gates ejecutados
por servidor, evidencia obligatoria vinculada a actor/bundle/versión/verdict/ID,
recibo/auditoría/outbox transaccionales, recuperación idempotente y clientes reales.
114 passed, 1 failed, 1 skipped en suite final. Fallo de calendario reproducido en
main exacto y no modificado. El skip PostgreSQL requiere su fixture explícito;
la prueba se ejecutó y pasó separadamente. Revisor: 76 passed SQLite/HTTPS/clientes,
76 passed PostgreSQL y 10 passed en cierres finales. No sumar ejecuciones solapadas.

No se añadió workflow CI ni se declara CI verde. La comprobación de reglas/checks
GitHub y revisión del SHA exacto se registra en la PR antes del merge, sin bypass.
La ausencia de protección/checks requeridos no transforma el fallo local en verde.

Backlog o límites: adapters de texto canónico DOF/licenciados (hoy fail-closed),
cobertura exhaustiva de claims y equivalencia visual general PDF/DOCX no son gates
adicionales aprobados en las fuentes accesibles. La política vigente exige evidencia
verificable y ambos gates; no garantiza corrección jurídica general. Extracción
lógica para formatos limitados está ligada a bytes/hash/texto/método. Trabajo histórico
de otro servidor/Surface no recuperado es límite de reconciliación, no bloqueo del
candidato aislado autorizado desde main. Sesión del host/IdP/proxy/ACL reales siguen
fuera de esta publicación. Ver slice0-local-validation.md para los límites completos.

## Delta respecto al paquete entregado

Se conserva byte por byte `legalize-mx-slice0-candidate-a1c2262-20261013.zip`, SHA256
`4c10e4d5a06aac4cf1a96a1d3e84150fd7ec4d5b120f73531a87f0576db0a07d`, guardado en Library.
Sus archivos funcionales conservan el contenido entregado, salvo la eliminación
de una línea vacía adicional al EOF de scripts/legal_release_gates.py, detectada
por git diff --check contra el commit publicado (sin cambio de comportamiento).
Este checkpoint es nuevo;
docs/legal-response-release-gate.md se actualiza para describir la CLI autenticada
y la evidencia persistente en vez de sus comandos históricos ya inválidos. Son
los deltas documentales de publicación. La corrección EOF es el único delta de
código y no modifica lógica ni tests; la revisión final usa el nuevo SHA exacto.

Eliminar approved directo impone la política ya documentada en
config/legal_response_release_policy.json y la regla operativa del release gate.
Los JSON canónicos no cambiaron. La API recibe execution_id/bundle y el servidor
determina verdict desde evidencia persistida; CLI/interfaz no eligen aprobación.
