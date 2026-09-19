# legalize-mx

Base de conocimiento juridica versionada para Mexico, orientada a retrieval y citacion para asistentes juridicos con RAG.

## Objetivo

`legalize-mx` no es un chatbot. Es la capa de datos juridicos que permite construir un asistente juridico con:

1. legislacion federal versionada
2. jurisprudencia federal estructurada
3. citas verificables
4. control de vigencia, jurisdiccion y fuente

## Alcance inicial

### Corpus principal

1. Constitucion Politica de los Estados Unidos Mexicanos
2. codigos federales vigentes
3. leyes federales vigentes

### Corpus complementario

1. jurisprudencia federal del SJF/SCJN
2. reglamentos federales
3. tratados internacionales

## Estructura

```text
legalize-mx/
├── connectors/
├── docs/
├── indexes/
├── mexico/
├── schemas/
├── scripts/
└── sources/
```

## Principios

1. La fuente oficial manda.
2. Legislacion y jurisprudencia viven en corpus separados.
3. La unidad de retrieval para leyes es articulo o fraccion.
4. La unidad de retrieval para jurisprudencia es el documento individual.
5. Toda respuesta del asistente debe incluir citas estructuradas.
6. Ninguna afirmacion jurisprudencial debe salir sin pasar un gate de evidencia local verificable.
7. Ninguna autoridad juridica debe salir como soporte liberable sin pasar primero un gate de resolucion de autoridad local o live verificable.

## Documentacion

El diseno de referencia esta resumido en [docs/architecture.md](docs/architecture.md).

La compuerta de no-invencion de jurisprudencia esta en [docs/jurisprudence-grounding-gate.md](docs/jurisprudence-grounding-gate.md).

La compuerta de resolucion de autoridad juridica esta en [docs/legal-authority-verification-gate.md](docs/legal-authority-verification-gate.md).

La ruta obligatoria de liberacion de escritos esta en [docs/legal-response-release-gate.md](docs/legal-response-release-gate.md).

El diseno del modo hibrido `Anthropic para razonamiento / local para talacha` esta en [docs/hybrid-model-routing.md](docs/hybrid-model-routing.md).

El patron colegiado para escritos juridicos de alto impacto esta en [docs/legal-panel-orchestrator.md](docs/legal-panel-orchestrator.md).

La consola operativa interna para observar corpus, colas, lotes y recibos esta en [docs/operator-console.md](docs/operator-console.md).

El backend inicial para expedientes, documentos versionados y actuaciones esta en [docs/expediente-backend.md](docs/expediente-backend.md).

Para una evaluacion basada en evidencia del sistema desde GitHub, consultar [docs/system-potential.md](docs/system-potential.md) y la [guia de analisis por GitHub](docs/github-analysis-guide.md). La frontera entre lo versionado, lo local y los datos heredados esta definida en [docs/data-versioning-policy.md](docs/data-versioning-policy.md).

## Estado

El repositorio ya contiene implementaciones para ingesta y normalizacion, manifests y chunks, gates de evidencia y autoridad, liberacion controlada de respuestas, backend de expedientes y consola operativa. Esto no acredita por si mismo cobertura completa del corpus, despliegue productivo, aceptacion juridica ni resultados de un caso concreto.

El estado de cada capacidad, sus rutas de evidencia y sus limites estan en [docs/system-potential.md](docs/system-potential.md). Antes de concluir disponibilidad o cobertura, ejecutar los checks y revisar los recibos vigentes del entorno correspondiente.

## Uso rapido del importador actual

La primera automatizacion disponible reconstruye los tres documentos piloto de legislacion federal desde una fuente declarativa:

```bash
python3 scripts/import_federal_legislation.py
```

Fuente:

`sources/federal_legislation_pilots.json`

## Operacion periodica

La ejecucion periodica queda soportada con:

1. runner de ciclo: [scripts/run_ingestion_cycle.py](/root/legalize-mx/scripts/run_ingestion_cycle.py)
2. scheduler de lote: [scripts/run_ingestion_batch.py](/root/legalize-mx/scripts/run_ingestion_batch.py)
3. unidades versionadas: [legalize-mx-ingestion.service](/root/legalize-mx/ops/systemd/legalize-mx-ingestion.service) y [legalize-mx-ingestion.timer](/root/legalize-mx/ops/systemd/legalize-mx-ingestion.timer)

Los snapshots por lote se guardan en:

`raw/diputados/logs/batch_runs/`
