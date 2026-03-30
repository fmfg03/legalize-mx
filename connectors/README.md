# Connectors

Cada conector debe encargarse de una fuente o modalidad de ingesta concreta.

## Directorios

1. `scjn_sjf_api/`: integracion directa con servicios o rutas de SJF.
2. `scjn_sij_api/`: integracion con SIJ.
3. `scjn_csv_import/`: importacion desde descargas estructuradas CSV/JSON.
4. `scjn_html_fallback/`: fallback para HTML cuando no exista via mas estable.
5. `state_congreso_tamaulipas/`: conector declarativo para legislacion vigente estatal de Tamaulipas.

## Regla

No mezclar scraping HTML con logica canonica de negocio.

## Cobertura estatal base

Existe una base declarativa para los 32 estados en:

`sources/state_connectors_base.json`

Esa base sigue siendo el fallback estructural por `edo_id` usando Orden Juridico Nacional.

La cobertura operativa ya se resuelve prioritariamente desde overrides especificos por estado en:

`sources/on_demand_connectors.json`

Estado actual:

1. `32` estados tienen override especifico por `state_code`
2. `11` estados tienen `seeded_target` utilizable para al menos un codigo civil
3. `21` estados quedan en `connector_route` verificado, listos para materializacion bajo demanda
4. el fallback `verified_ojn_fallback` queda como respaldo, no como ruta primaria
