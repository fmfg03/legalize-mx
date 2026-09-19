# Guia para analizar legalize-mx desde GitHub

## Alcance del analisis

La conexion de GitHub permite analizar el contenido publicado y autorizado del repositorio: codigo, README y documentacion. No entrega los archivos locales ignorados, secretos, bases de datos, expedientes, payloads crudos, logs de ejecucion ni el estado de servicios en tiempo real.

Antes de analizar, leer:

1. `README.md`
2. `docs/system-potential.md`
3. `docs/data-versioning-policy.md`
4. `docs/architecture.md`

## Rutas por pregunta

| Pregunta | Rutas de inicio |
| --- | --- |
| Que problema resuelve el sistema | `README.md`, `docs/system-potential.md`, `docs/architecture.md` |
| Como se obtiene y transforma jurisprudencia | `docs/jurisprudence-ingestion-plan.md`, `scripts/fetch_scjn_jurisprudence_*.py`, `scripts/normalize_scjn_*.py` |
| Como evita citas o autoridades no verificadas | `docs/jurisprudence-grounding-gate.md`, `docs/legal-authority-verification-gate.md`, `scripts/validate_*` |
| Como se libera una respuesta | `docs/legal-response-release-gate.md`, `scripts/release_legal_response.py` |
| Que ofrece el producto de expedientes | `docs/expediente-backend.md`, `backend/`, `tests/backend/` |
| Que ofrece la experiencia operativa | `docs/operator-console.md`, `ops/`, `scripts/run_operator_console.py` |
| Que datos no estan en GitHub | `docs/data-versioning-policy.md`, `.gitignore` |

## Prompts recomendados

- "Analiza `fmfg03/legalize-mx` como plataforma juridica: separa capacidades implementadas, parciales y no verificadas; cita rutas concretas."
- "Traza el flujo desde una fuente SJF hasta la liberacion de una respuesta. Identifica cada gate, su entrada, salida y evidencia persistida."
- "Revisa el modelo de confianza del repositorio. Busca rutas que permitan una cita sin evidencia y distingue hechos comprobados de supuestos."
- "Evalua la madurez del backend de expedientes y del workspace: API, auditoria, autenticacion, almacenamiento, pruebas y huecos operativos."
- "Propone los siguientes experimentos o evaluaciones para demostrar cobertura, actualidad y recuperacion, sin asumir que los archivos locales estan publicados."

## Disciplina de conclusiones

Cada conclusion debe incluir una de estas etiquetas:

- **Verificado en repositorio:** tiene ruta y evidencia versionada.
- **Parcial:** existe implementacion, pero falta evidencia de cobertura, ejecucion o aceptacion.
- **No verificable desde GitHub:** depende de datos ignorados, servicios, credenciales, produccion o revision profesional.

No interpretar una ruta de `raw/`, `mexico/` o `indexes/` como prueba de que todo su contenido local esta publicado. Las reglas exactas y los datos heredados estan descritos en la politica de versionado.

## Conexion y permisos

En ChatGPT, conectar GitHub desde **Configuracion > Aplicaciones o Plugins > GitHub**, autorizar la aplicacion y seleccionar solo este repositorio. La disponibilidad depende del plan y de la superficie de ChatGPT. La aplicacion de GitHub es de lectura para analisis; no habilita cambios ni pushes al repositorio. Consultar la [documentacion oficial de OpenAI](https://help.openai.com/es-419/articles/11145903-conectar-github-con-chatgpt) para los pasos y controles vigentes.
