# Arquitectura

Este repositorio materializa el esquema base de `legalize-mx`.

## Resumen operativo

1. `mexico/legislation/` almacena normas federales normalizadas en Markdown.
2. `mexico/jurisprudence/` almacena tesis y precedentes normalizados.
3. `mexico/chunks/` contiene las unidades de retrieval.
4. `indexes/` contiene manifests y JSONL listos para indexacion.
5. `sources/` define fuentes y niveles de confianza.
6. `schemas/` define contratos de datos para validacion.

## Regla central

La consulta del asistente juridico debe resolverse contra almacenamiento local e indices propios.

Las fuentes externas se usan para:

1. sincronizacion
2. backfill
3. verificacion puntual

## Prioridades tecnicas

1. ingestar corpus federal vigente
2. chunking por articulo para normas
3. chunking por seccion para jurisprudencia
4. citas estructuradas
5. versionado temporal
