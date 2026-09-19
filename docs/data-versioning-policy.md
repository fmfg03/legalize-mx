# Politica de versionado y frontera de datos

## Objetivo

`legalize-mx` usa GitHub como superficie de codigo, contratos y analisis. El corpus masivo y los artefactos operativos se conservan localmente o en una entrega de datos gobernada; no se agregan de forma incidental a commits.

## Clasificacion

| Clase | Destino previsto | Ejemplos | Regla |
| --- | --- | --- | --- |
| Codigo, contratos y documentacion | Git | `backend/`, `scripts/`, `schemas/`, `sources/`, `docs/`, pruebas y configuracion sin secretos | Versionar con pruebas y documentacion. |
| Fixtures pequenos y no sensibles | Git | `fixtures/` seleccionados | Deben ser minimizados, reproducibles y no contener expedientes o credenciales. |
| Corpus e indices ya rastreados | Git heredado | Entradas existentes bajo `mexico/` e `indexes/` | Se conservan sin alteracion en esta entrega; no son prueba de cobertura, actualidad ni disponibilidad productiva. |
| Corpus canonico e indices generados nuevos | Local o entrega de datos aprobada | Nuevos SJF bajo `mexico/jurisprudence/sjf/` y JSONL generados | No agregar por defecto. Publicarlos o migrar los heredados requiere una decision y revision de tamano, licencia, trazabilidad y costo. |
| Payloads, snapshots y estado operativo | Solo local | `raw/`, catalogos, logs, caches, recibos y releases | Nunca agregar de forma incidental. Conservarlos con sus controles operativos. |
| Expedientes, borradores y evidencia de caso | Solo local | `storage/expedientes/`, `drafts/`, archivos PDF/DOCX/imagen | Nunca versionar en este repositorio sin autorizacion expresa y una revision de confidencialidad. |
| Secretos y configuracion efectiva | Solo local o gestor de secretos | `.env`, llaves, tokens, cadenas de conexion | Nunca versionar. Usar solo plantillas sin valores sensibles. |

## Regla de compatibilidad con el estado actual

Las reglas de `.gitignore` aplican a archivos no rastreados. No eliminan, ocultan de Git ni desindexan rutas ya versionadas. En particular, esta politica no modifica los corpus ni los indices historicos presentes en el repositorio; una migracion de datos es un cambio separado, recuperable y sujeto a aprobacion.

## Trazabilidad de datos fuera de Git

Todo conjunto de datos que se use para una conclusion juridica o una corrida debe conservar, fuera de este repositorio cuando sea necesario:

1. fuente y URL oficial o licencia aplicable;
2. identificador documental o de lote;
3. fecha de captura y estado de ejecucion;
4. checksum del contenido y metadata relevante;
5. manifiesto o recibo que permita reconstruir la relacion entre fuente, documento normalizado e indice.

Los scripts, esquemas y manifests versionados describen el mecanismo; no sustituyen el artefacto de datos ni su evidencia de ejecucion.

## Controles antes de un commit

1. Revisar `git status --short` y confirmar que no haya `raw/`, corpus generado, expedientes o binarios de caso.
2. Usar `git check-ignore --no-index <ruta>` para comprobar la politica sobre rutas nuevas.
3. Agregar archivos por ruta y proposito; no usar `git add -A` en un arbol con datos locales.
4. Separar un cambio de codigo/documentacion de cualquier propuesta de migracion o publicacion de datos.

## Cambios a esta politica

Cambiar que datos se publican, desindexar contenido existente, borrar artefactos o mover corpus a otro almacenamiento requiere una propuesta separada que identifique alcance, recuperacion, licencia, privacidad y autorizacion.
