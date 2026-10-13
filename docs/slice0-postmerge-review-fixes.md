# Slice 0 — correcciones acotadas de revisión automática

La PR 2 se fusionó en bc73b7496312bbae960429842eb0e0d30de06ee4, tras revisión
independiente del SHA exacto y sin gates GitHub obligatorios. La revisión automática
adicional terminó después y publicó cuatro hallazgos relacionados. Se atienden bajo
la autorización hasta merge; no hay despliegue ni cambios de infraestructura,
credenciales, permisos, dependencias o políticas JSON canónicas. Paquete inicial
inmutable. Este documento registra el delta; las evidencias previas no se sustituyen.

## Contrato de corrección y pruebas previstas

1. Persistir snapshots de políticas del servidor dentro de la evidencia y verificar
   sus hashes/IDs requeridos al validar ejecución/recibo/outbox. Así se admiten IDs
   versionados coherentes, sin depender de la política actual durante exportación.
   Evidencia anterior sin snapshot conserva validación de los dos IDs v1 originales;
   snapshot presente pero inválido se rechaza, sin fallback ni migración de evidencia.
2. Tras validar reviewer activo, actor/expediente, integridad de ejecución y mismo
   bundle, devolver recibo existente íntegro antes de comprobar inputs mutables.
   Documento/políticas/índices/expiry actuales se verifican para primera liberación;
   no cambian una decisión ya comprometida. Retry no duplica audit/outbox.
3. Restaurar route/method y registrar canal interno/REST API key/MCP OAuth y tool
   desde los handlers del servidor; nunca desde argumentos o metadata del cliente.
   Comprobar auditoría REST y MCP en flujos reales y retry sin entradas duplicadas.
4. Fijar git archive del fixture a main histórico
   a1c226260019c0da40d45eff2d1fa5dd42b40ce4, en vez de HEAD. Se reprodujo el fallo
   tras commit: HEAD ya crea tablas nuevas antes del upgrade 0003. Verificar el test
   ejecutado con HEAD publicado además de working tree; equivalencia de archivos
   previa no cubría esta dependencia de contexto y no debe presentarse como prueba.

Ejecutar regresiones pertinentes de auth/evidencia/formato/migración/HTTP/clientes;
no repetir suites ajenas o cambiar el fallo heredado de calendario. Revisar el nuevo
SHA exacto y leer reglas/checks/revisiones antes del merge de correcciones. Los límites
semánticos/visuales/históricos/productivos del candidato permanecen explícitos.

## Verificación del working tree

93 contratos relacionados aprobados (auth, evidencia, formatos, migración, auditoría,
HTTPS/JWKS/CLI/interfaz); 41 tests de evidencia/liberación aprobados, incluidos los
casos nuevos. Los grupos se solapan, no se suman. Cuatro regresiones con cambios
físicos de política/índice/documento/caducidad aprobadas aparte; no modifican la
auditoría original al reintentar por otro canal. El test migratorio se volverá a
ejecutar sobre el nuevo SHA publicado para comprobar el contexto HEAD corregido.
La revisión automática previa terminó con hallazgos, no con aprobación; no se
presenta su estado Completed como ausencia de problemas ni como CI verde.
