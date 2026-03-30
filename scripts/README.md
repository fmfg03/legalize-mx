# Scripts

Este directorio alojara scripts para:

1. ingesta de leyes federales
2. ingesta de jurisprudencia
3. normalizacion
4. generacion de chunks
5. validacion de schemas
6. reconstruccion de indices

## Scripts actuales

### `import_federal_legislation.py`

Genera documentos Markdown, manifiesto federal y chunks de legislacion a partir de una fuente declarativa JSON.

Ejemplo:

```bash
python3 scripts/import_federal_legislation.py
```

Fuente por defecto:

`sources/federal_legislation_pilots.json`

### `fetch_diputados_metadata.py`

Descarga fichas `ref/*.htm` de la Camara de Diputados y extrae metadatos base para bootstrap de inventario federal.

Ejemplos:

```bash
python3 scripts/fetch_diputados_metadata.py --ids cpeum ccf cpf
python3 scripts/fetch_diputados_metadata.py --ids-file ids.txt --output /tmp/diputados.json
```

Salida:

1. `title`
2. `short_title`
3. `category`
4. `rank`
5. `last_reform_date`
6. `publication_dates`
7. `source_url`

### `fetch_diputados_catalog.py`

Descubre el inventario base desde `https://www.diputados.gob.mx/LeyesBiblio/index.htm`.

Extrae por entrada:

1. `source_id`
2. `source_url`
3. `title`
4. `short_title`
5. `category`
6. `rank`
7. `last_reform`

Ejemplos:

```bash
python3 scripts/fetch_diputados_catalog.py
python3 scripts/fetch_diputados_catalog.py --output /tmp/catalog.json
```

### `bootstrap_federal_inventory.py`

Orquesta:

1. catalogo federal
2. enriquecimiento por fichas `ref/*.htm`
3. salida de inventario reutilizable

Ejemplos:

```bash
python3 scripts/bootstrap_federal_inventory.py --skip-metadata
python3 scripts/bootstrap_federal_inventory.py --limit 20 --output /tmp/inventory.json
python3 scripts/bootstrap_federal_inventory.py --catalog-output /tmp/catalog.json --output /tmp/inventory.json
```

### `parse_legislation_plaintext.py`

Convierte texto plano de una norma individual a un JSON compatible con `import_federal_legislation.py`.

Ejemplo:

```bash
python3 scripts/parse_legislation_plaintext.py \
  --metadata /tmp/ccf-meta.json \
  --text /tmp/ccf.txt \
  --output /tmp/ccf-import.json
```

### `extract_diputados_pdf_text.py`

Descarga un PDF desde `LeyesBiblio/pdf/*.pdf`, lo guarda en `raw/diputados/pdf/` y extrae texto plano a `raw/diputados/text/`.

Requiere `pypdf` en la venv del proyecto.

Ejemplos:

```bash
/root/legalize-mx/.venv/bin/python scripts/extract_diputados_pdf_text.py --source-id ccf
/root/legalize-mx/.venv/bin/python scripts/extract_diputados_pdf_text.py --source-id cpf --output-text /tmp/cpf.txt --output-meta /tmp/cpf-extract.json
```

### `ingest_diputados_norm.py`

Wrapper end-to-end para una sola norma:

1. metadata
2. PDF
3. texto plano
4. parsing por articulos
5. upsert en Markdown/manifests/chunks

El script ahora devuelve un JSON de estado con:

1. etapa de metadata
2. etapa de texto
3. etapa de parseo
4. etapa de importacion
5. errores acumulados

Ejemplos:

```bash
/root/legalize-mx/.venv/bin/python scripts/ingest_diputados_norm.py --source-id ccf
/root/legalize-mx/.venv/bin/python scripts/ingest_diputados_norm.py --source-id cpf --text-file /tmp/cpf.txt
/root/legalize-mx/.venv/bin/python scripts/ingest_diputados_norm.py --source-id ccf --metadata-file /tmp/ccf-meta.json --text-file /tmp/ccf.txt
/root/legalize-mx/.venv/bin/python scripts/ingest_diputados_norm.py --source-id ccf --allow-partial
```

### `drain_diputados_queue.py`

Reintenta trabajos pendientes encolados cuando el portal de Diputados estuvo lento o caido.

Ejemplos:

```bash
python3 scripts/drain_diputados_queue.py
python3 scripts/drain_diputados_queue.py --limit 20
```

### `run_ingestion_batch.py`

Scheduler secuencial para lotes de ingesta. Orquesta:

1. seleccion de `source_id`
2. consulta del log para `resume`
3. ejecucion de `ingest_diputados_norm.py` por norma
4. corte por umbral de errores
5. drenado opcional de cola

Importante:

Ejecutalo con la venv del proyecto para que el wrapper unitario use el mismo interprete que ya tiene `pypdf`.

Ejemplos:

```bash
/root/legalize-mx/.venv/bin/python scripts/run_ingestion_batch.py --source-ids ccf cpf --allow-partial
/root/legalize-mx/.venv/bin/python scripts/run_ingestion_batch.py --inventory-file /tmp/inventory.json --resume-from-log --retry-partials --drain-queue
/root/legalize-mx/.venv/bin/python scripts/run_ingestion_batch.py --source-ids-file ids.txt --max-errors 5 --sleep-between 1
```

Fixtures locales opcionales para pruebas:

1. `--metadata-dir /tmp` busca `<source_id>-meta.json`
2. `--text-dir /tmp` busca `<source_id>.txt` o `<source_id>-offline.txt`

### `run_ingestion_cycle.py`

Runner de ciclo para operacion periodica. Ejecuta `run_ingestion_batch.py` y guarda un snapshot JSON por lote en:

`raw/diputados/logs/batch_runs/`

Tambien actualiza:

`raw/diputados/logs/batch_runs/latest.json`

Ejemplos:

```bash
/root/legalize-mx/.venv/bin/python scripts/run_ingestion_cycle.py --source-ids ccf --metadata-dir /tmp --text-dir /tmp --refresh
/root/legalize-mx/.venv/bin/python scripts/run_ingestion_cycle.py --source-ids-file ops/ingestion/source_ids.txt --resume-from-log --retry-partials --drain-queue
```

### `resolve_missing_norm.py`

Resolvedor de normas fuera del stack local. Hace:

1. busca primero en `indexes/legislation_manifest.jsonl`
2. si no encuentra, busca un conector configurado
3. devuelve una ruta de materializacion sin descargar nada
4. opcionalmente encola la solicitud

Ejemplos:

```bash
python3 scripts/resolve_missing_norm.py --query "Codigo Civil Federal"
python3 scripts/resolve_missing_norm.py --query "Codigo Civil de Tamaulipas" --jurisdiction state --state-code tam --document-type code
python3 scripts/resolve_missing_norm.py --query "Codigo Civil de Tamaulipas" --jurisdiction state --state-code tam --document-type code --enqueue
```

Cobertura actual:

1. `32` conectores estatales base por `state_code` siguen existiendo como fallback estructural
2. `32` estados ya tienen override especifico en `sources/on_demand_connectors.json`
3. `11` overrides resuelven a `external_target` para al menos un codigo civil
4. `21` overrides resuelven a `connector_route` verificado para materializacion bajo demanda
5. el fallback `verified_ojn_fallback` queda como respaldo cuando un override se retire o falle

### `validate_jurisprudence_grounding.py`

Gate de evidencia para bloquear salidas juridicas que inventen jurisprudencia.

Valida:

1. que el bundle tenga `response_text`, `citations` y `claims`
2. que las citas jurisprudenciales coincidan con el indice local
3. que la `quote` declarada exista en el chunk local y coincida con `quote_sha256`
4. que cualquier claim `jurisprudence` o `mixed` tenga soporte jurisprudencial verificado
5. que la respuesta no mencione jurisprudencia sin evidencia local

Ejemplos:

```bash
python3 scripts/validate_jurisprudence_grounding.py --bundle fixtures/assistant_response_pass_no_jurisprudence.json
python3 scripts/validate_jurisprudence_grounding.py --bundle fixtures/assistant_response_fail_fake_jurisprudence.json
```

Recibos:

`raw/guardrails/receipts/jurisprudence_grounding_gate_receipts.jsonl`

### `release_legal_response.py`

Ruta obligatoria de liberacion de escritos juridicos.

Hace:

1. corre el gate jurisprudencial
2. escribe recibo del gate
3. escribe recibo de liberacion
4. mueve el bundle a `approved` o `blocked`

Ejemplos:

```bash
python3 scripts/release_legal_response.py --bundle fixtures/assistant_response_pass_no_jurisprudence.json
python3 scripts/release_legal_response.py --bundle fixtures/assistant_response_fail_fake_jurisprudence.json
```

Artefactos:

1. `raw/guardrails/receipts/legal_response_release_receipts.jsonl`
2. `raw/guardrails/releases/approved/`
3. `raw/guardrails/releases/blocked/`

### `route_model_execution.py`

Router declarativo para separar:

1. `anthropic_api` para razonamiento juridico complejo
2. `local_ollama` para trabajo operativo
3. `hybrid` para escritos liberables con gate obligatorio

Ejemplo:

```bash
python3 scripts/route_model_execution.py --task /tmp/task.json
```

### `legal_panel_orchestrator.py`

Panel colegiado juridico con:

1. primera ronda sellada
2. commitments
3. reveal post-deliberacion
4. bloqueo de drift injustificado
5. perfiles por materia
6. veto y escalacion por rol critico
7. release gate final

Ejemplos:

```bash
python3 scripts/legal_panel_orchestrator.py --session fixtures/legal_panel_session_pass.json
python3 scripts/legal_panel_orchestrator.py --session fixtures/legal_panel_session_fail_vote_drift.json
```

Artefactos:

1. `raw/legal_panel/candidates/`
2. `raw/guardrails/receipts/legal_panel_receipts.jsonl`

### `fetch_scjn_jurisprudence_catalog.py`

Descubre catálogos jurisprudenciales desde la API oficial del Repositorio SCJN en `bicentenario.scjn.gob.mx/repositorio-scjn`.

Para `tesis`, la ruta real queda así:

1. `GET /api/reforma/fuentes/1`
2. resolver `indice: "tesis"`
3. `GET /api/v1/tesis/count`
4. `GET /api/v1/tesis/ids?page=N&size=M`
5. `GET /api/v1/tesis/default`

Ejemplo:

```bash
python3 scripts/fetch_scjn_jurisprudence_catalog.py --document-kind tesis
python3 scripts/fetch_scjn_jurisprudence_catalog.py --document-kind tesis --max-pages 2 --page-size 1000
```

### `fetch_scjn_jurisprudence_documents.py`

Descarga payloads crudos desde el catálogo local y escribe snapshots en `raw/scjn/snapshots/`.

Ejemplo:

```bash
python3 scripts/fetch_scjn_jurisprudence_documents.py --catalog raw/scjn/catalog/tesis_catalog.json
python3 scripts/fetch_scjn_jurisprudence_documents.py --catalog raw/scjn/catalog/tesis_catalog.json --limit 5
```

### `normalize_scjn_jurisprudence_document.py`

Normaliza payloads crudos SCJN para `precedente`, `voto` y `acuerdo`.

Ejemplo:

```bash
python3 scripts/normalize_scjn_jurisprudence_document.py --document-kind precedente --input /tmp/precedente_raw.json --output /tmp/precedente_doc.json
```

### `run_scjn_jurisprudence_batch.py`

Orquestador incremental por página del API oficial SCJN.

Persistencia:

`raw/scjn/state/{document_kind}_batch_state.json`

Ejemplos:

```bash
python3 scripts/run_scjn_jurisprudence_batch.py --document-kind tesis --page-size 10 --pages-per-run 1
python3 scripts/run_scjn_jurisprudence_batch.py --document-kind precedente --page-size 5 --pages-per-run 1
python3 scripts/run_scjn_jurisprudence_batch.py --all-kinds --page-size 5 --pages-per-run 1
```

### `normalize_scjn_tesis.py`

Normaliza un payload crudo de tesis a documento canónico JSON.

Ejemplo:

```bash
python3 scripts/normalize_scjn_tesis.py --input /tmp/tesis_raw.json --output /tmp/tesis_doc.json
```

### `build_jurisprudence_manifest.py`

Reconstruye `indexes/jurisprudence_manifest.jsonl` desde documentos canónicos.

Ejemplo:

```bash
python3 scripts/build_jurisprudence_manifest.py
```

### `build_jurisprudence_chunks.py`

Genera `indexes/jurisprudence_chunks.jsonl` desde el manifest jurisprudencial.

Ejemplo:

```bash
python3 scripts/build_jurisprudence_chunks.py
```

### `emit_jurisprudence_ingestion_receipt.py`

Emite un recibo de lote para la ingesta jurisprudencial.

Ejemplo:

```bash
python3 scripts/emit_jurisprudence_ingestion_receipt.py
```

## Cache y cola

Los fetchers de Diputados ahora:

1. guardan cache persistente en `raw/diputados/cache/`
2. usan cache vieja si la red falla
3. encolan descargas fallidas en `raw/diputados/queue/pending_downloads.jsonl`

## Ingestion log

Las ejecuciones del wrapper `ingest_diputados_norm.py` ahora registran una linea JSON por corrida en:

`raw/diputados/logs/ingestion_log.jsonl`

Cada linea incluye:

1. `logged_at`
2. `run_id`
2. `source_id`
3. `status`
4. `started_at`
5. `finished_at`
6. `exit_code`
7. resultado por etapa: `metadata`, `text`, `parse`, `import`
8. `errors`
9. `duration_ms`
