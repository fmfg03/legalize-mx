# Legal Authority Verification Gate

La compuerta de grounding jurisprudencial ya no basta por si sola.

Si una cita existe en fuente oficial pero todavia no vive en el indice local, el sistema necesita una verificacion puntual autorizada antes de decidir si:

1. materializa la fuente,
2. deja pasar el bundle con evidencia suplementaria verificable,
3. o bloquea la liberacion.

## Ruta correcta

1. resolver local contra `indexes/`
2. si falta evidencia local, resolver live contra fuente autorizada
3. producir chunks suplementarios verificables
4. pasar esos chunks al grounding gate
5. liberar solo si:
   - authority gate = `PASS`
   - grounding gate = `PASS`

## Fuentes v1

1. `SCJN/SJF` para jurisprudencia federal
2. `Diputados` y `DOF` para legislacion federal
3. providers licenciados via adapters separados:
   - `vLex`
   - `Westlaw`
   - `Lexis`
   - `Tirant`

## Limite honesto

Esto no convierte a `legalize-mx` en asesor juridico.

Hace una cosa: verificar autoridad citada antes de liberar work product juridico.
