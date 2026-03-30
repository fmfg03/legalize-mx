# Indexes

Archivos esperados:

1. `legislation_manifest.jsonl`
2. `jurisprudence_manifest.jsonl`
3. `legislation_chunks.jsonl`
4. `jurisprudence_chunks.jsonl`

Estos archivos se mantienen fuera del contenido fuente y se regeneran a partir de `mexico/`.

Para jurisprudencia, el flujo correcto es:

1. documentos canónicos en `mexico/jurisprudence/`
2. `jurisprudence_manifest.jsonl` reconstruido desde esos documentos
3. `jurisprudence_chunks.jsonl` reconstruido desde el manifest

No indexar payload crudo de SCJN directamente.
