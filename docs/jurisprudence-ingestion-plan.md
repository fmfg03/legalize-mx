# Ingesta de Jurisprudencia

El poblamiento inicial debe empezar por `tesis`.

No por volumen. Por control citacional.

## Regla

La unidad canónica inicial es:

1. `tesis` del SJF/SCJN

La unidad canónica posterior es:

1. `precedente`
2. `voto`
3. `acuerdo`

## Flujo

1. `fetch_scjn_jurisprudence_catalog.py`
   - consume inventario remoto
   - emite lista de registros a descargar
2. `fetch_scjn_jurisprudence_documents.py`
   - descarga payload bruto por `registry_id`
   - guarda snapshot y metadata cruda en `raw/scjn/`
3. `normalize_scjn_tesis.py`
   - convierte payload crudo a documento canónico
   - emite Markdown o JSON normalizado en `mexico/jurisprudence/sjf/tesis/`
4. `build_jurisprudence_manifest.py`
   - recompone `indexes/jurisprudence_manifest.jsonl`
5. `build_jurisprudence_chunks.py`
   - genera `indexes/jurisprudence_chunks.jsonl`
6. `emit_jurisprudence_ingestion_receipt.py`
   - deja recibo de lote con hashes, conteos y fallos

## Estructura de almacenamiento

```text
raw/scjn/
├── catalog/
├── payloads/
│   └── tesis/
├── pdf/
│   └── tesis/
└── receipts/

mexico/jurisprudence/sjf/
├── tesis/
├── precedentes/
├── votos/
└── acuerdos/
```

## Clave documental

Para `tesis`, la clave primaria es:

1. `registry_id`

La clave derivada de repositorio es:

1. `doc_id = mx-sjf-tesis-{registry_id}`

## Reglas de normalización para tesis

Campos mínimos:

1. `registry_id`
2. `rubro`
3. `text`
4. `type`
5. `epoch`
6. `instance`
7. `organ`
8. `matter`
9. `publication_date`
10. `source_url`
11. `citation_label`
12. `source_payload_path`
13. `text_checksum_sha256`
14. `metadata_checksum_sha256`

## Chunking

Para `tesis`:

1. chunk `rubro`
2. chunk `texto`
3. chunk `precedentes`, si existe

No se debe dividir una tesis en fragmentos arbitrarios por longitud. La prioridad es preservar trazabilidad citacional.

## Criterio de indexación

Cada chunk debe permitir:

1. búsqueda por `registro digital`
2. búsqueda por `rubro`
3. recuperación semántica por `texto`
4. resolución exacta de cita

## Regla de salida del asistente

Ninguna mención a jurisprudencia puede pasar si:

1. el `registry_id` no existe en `indexes/jurisprudence_chunks.jsonl`
2. la cita no tiene `source_url`
3. la `quote` no aparece en el chunk local
4. el gate de grounding falla
