# Hybrid Model Routing

Tu formulacion original mezcla dos capas distintas:

1. `pensar`
2. `hacer`

No deben correr siempre en el mismo modelo.

La separacion correcta es:

1. `Anthropic API` para deliberacion juridica compleja
2. `modelo local` para talacha operativa
3. `guardrails locales` para liberar cualquier escrito

## Politica

`config/hybrid_model_routing_policy.json`

## Conexion de proveedores

`config/model_provider_connections.example.json`

## Request schema

`schemas/hybrid_task_request.schema.json`

## Router

`scripts/route_model_execution.py`

## Rutas

### `local_ollama`

Para:

1. retrieval
2. chunking
3. clasificacion
4. normalizacion
5. formateo de citas
6. limpieza de borrador

### `anthropic_api`

Para:

1. seleccion de teoria del caso
2. priorizacion de argumentos
3. analisis de riesgo
4. spotting de conflictos normativos
5. recomendaciones complejas

### `hybrid`

Para:

1. demandas
2. escritos
3. recomendaciones de alto impacto
4. conclusiones con jurisprudencia

En `hybrid` la secuencia correcta es:

1. razonamiento en proveedor fuerte
2. ejecucion y estructuracion local
3. `legal_panel_orchestrator.py`
4. `release_legal_response.py`

El panel juridico replica el patron fuerte de colegialidad:

1. primera ronda sellada
2. commitments
3. reveal post-deliberacion
4. bloqueo de drift sin justificacion estructurada
5. `merkle_root` local del protocolo de voto
6. perfiles por materia con veto y escalacion por rol critico

## Importante

Todavia no hay conexion viva a Anthropic.

Eso no es un hueco accidental. Falta:

1. clave API
2. politica de costos
3. contrato de prompts
4. limites de datos sensibles
5. decision de retencion y logging
