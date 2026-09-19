# Potencial del sistema y mapa de evidencia

## Proposito

Este documento permite evaluar `legalize-mx` desde un clon de GitHub sin confundir codigo versionado con disponibilidad productiva, cobertura completa del corpus o asesoria juridica. Cada capacidad se presenta con la ruta que permite inspeccionarla.

## Mapa del sistema

```text
Fuentes declaradas y oficiales
        |
        v
Ingesta y normalizacion local
        |
        +--> raw/ (payloads, snapshots y recibos locales)
        |
        v
Documentos canonicos y manifests
        |
        v
Indices y gates de evidencia
        |
        +--> liberacion controlada de respuestas
        |
        +--> backend de expedientes y workspace Lexera
```

## Capacidades con evidencia

| Dominio | Estado en el codigo | Evidencia principal | Limite que no debe inferirse |
| --- | --- | --- | --- |
| Fuentes, esquemas y contratos | Implementado | `sources/`, `schemas/`, `connectors/` | Que todas las fuentes esten disponibles o actualizadas. |
| Ingesta y normalizacion federal/SJF | Implementado | `scripts/import_federal_legislation.py`, `scripts/fetch_scjn_jurisprudence_*.py`, `scripts/normalize_scjn_*.py` | Cobertura total, ejecucion reciente o exito de una corrida concreta. |
| Manifests, chunks y trazabilidad | Implementado | `scripts/build_*`, `indexes/README.md`, `docs/jurisprudence-ingestion-plan.md` | Que cada entrada local este publicada en GitHub. |
| Grounding jurisprudencial | Implementado | `scripts/validate_jurisprudence_grounding.py`, `docs/jurisprudence-grounding-gate.md` | Que una respuesta o escrito especifico haya sido aprobado. |
| Resolucion de autoridad y liberacion | Implementado | `scripts/validate_legal_authority.py`, `scripts/release_legal_response.py`, `docs/legal-response-release-gate.md` | Validez profesional de un escrito, fuente live disponible o presentacion formal. |
| Backend de expedientes y auditoria | Implementado | `backend/`, `docs/expediente-backend.md`, `tests/backend/` | Despliegue, configuracion segura o usuarios reales. |
| Consola y workspace Lexera | Implementado | `ops/`, `scripts/run_operator_console.py`, `docs/operator-console.md`, `tests/test_workspace_*.py` | UAT, conexion a servicios externos o operacion publica. |
| Retrieval con embeddings | Parcial | `indexes/`, `vectorstore/` y `embeddings/` estan definidos como superficies de datos | Un indice vectorial servido, actualizado o evaluado. |

## Flujo de confianza

1. Las fuentes declaradas alimentan scripts de ingesta y normalizacion.
2. Los documentos canonicos producen manifests y chunks trazables.
3. Una cita debe poder resolverse contra evidencia local o mediante el resolvedor autorizado antes de integrarse a una respuesta liberable.
4. La ruta de liberacion registra recibos y bloquea el bundle cuando falla un gate requerido.
5. El backend y el workspace organizan expedientes y actuaciones, pero no sustituyen la revision profesional ni otorgan autoridad juridica.

## Potencial evaluable desde GitHub

Un analisis puede determinar la separacion entre datos crudos, documentos canonicos, indices y decisiones de liberacion; revisar contratos y pruebas; ubicar superficies de seguridad; y proponer rutas de maduracion. Tambien puede comparar el diseno con los riesgos operativos expresados en el repositorio.

Un analisis no puede afirmar, solo con este repositorio, que el corpus sea exhaustivo o vigente, que los servicios esten desplegados, que un escrito se haya presentado, ni que una conclusion sea asesoria juridica. Esas afirmaciones requieren evidencia actual del entorno y, cuando corresponda, revision profesional.

## Ruta de evaluacion recomendada

1. Empezar por `README.md`, este documento y `docs/architecture.md`.
2. Revisar `docs/data-versioning-policy.md` antes de usar conteos o asumir que una ruta local esta publicada.
3. Seguir los flujos en `docs/jurisprudence-ingestion-plan.md`, `docs/legal-response-release-gate.md` y `docs/expediente-backend.md`.
4. Contrastar cada afirmacion con archivos, pruebas o recibos publicados; etiquetar lo no verificable como tal.
