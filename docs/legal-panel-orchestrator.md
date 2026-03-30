# Legal Panel Orchestrator

No basta con decir "varios modelos debatieron".

Si no controlas:

1. independencia inicial del voto
2. drift entre rondas
3. evidencia del reveal
4. bloqueo final por jurisprudencia

entonces no tienes colegialidad fuerte. Tienes agregacion opaca.

Tampoco sirve un panel unico universal. Civil, penal y amparo exigen oposiciones distintas.

## Artefactos

1. `scripts/legal_panel_orchestrator.py`
2. `scripts/legal_panel_vote_evidence.py`
3. `config/legal_panel_policy.json`
4. `schemas/legal_panel_session.schema.json`
5. `schemas/legal_panel_output.schema.json`

## Flujo

1. recibir una sesion con `draft_bundle`
2. validar `initial_vote_round`
3. validar `final_vote_round`
4. bloquear cualquier cambio de voto sin `structured_change_justification`
5. construir `initial_vote_commitments`
6. construir `vote_evidence` con `evidence_chain_id`, `events` y `merkle_root`
7. adjuntar `panel_metadata` al bundle
8. pasar el bundle por `release_legal_response.py`

## Politica del panel

`config/legal_panel_policy.json`

La politica ahora trabaja con perfiles por materia.

Perfiles iniciales:

1. `civil_damage`
2. `penal_defense`
3. `amparo`
4. `amparo_suspension`
5. `amparo_suspension_oficio`
6. `amparo_suspension_parte`

Ejemplo `civil_damage`:

1. `litigante_actor`
2. `abogado_contraparte`
3. `juzgador_revisor`
4. `revisor_probatorio`
5. `revisor_jurisprudencial`

Reglas:

1. `approve` y `conditional` pueden seguir a release
2. `reject` y `abstain` bloquean
3. el drift de voto exige `trigger`, `evidence_delta` y `reasoning_delta`
4. ciertos roles criticos pueden vetar o escalar aunque haya mayoria aprobatoria

Ejemplo:

1. si `revisor_jurisprudencial` vota `reject`, se bloquea
2. si `revisor_jurisprudencial` vota `conditional`, se escala
3. la mayoria ya no decide sola

Ejemplo `amparo`:

1. `abogado_quejoso`
2. `autoridad_responsable_revisor`
3. `tercero_interesado_revisor`
4. `secretario_proyectista_revisor`
5. `revisor_procedencia_amparo`
6. `revisor_jurisprudencial`

Reglas materiales en `amparo`:

1. `revisor_procedencia_amparo = reject` bloquea
2. `revisor_procedencia_amparo = conditional` escala
3. `secretario_proyectista_revisor = reject` bloquea
4. `secretario_proyectista_revisor = conditional` escala
5. `revisor_jurisprudencial = reject` bloquea

Ademas, `amparo` ya exige metadata estructurada en votos criticos:

1. `metadata.amparo.acto_reclamado_status`
2. `metadata.amparo.interes_status`
3. `metadata.amparo.definitividad_status`
4. `metadata.amparo.suspension_status`
5. `metadata.amparo.proyecto_madurez`

Controles materiales:

1. `acto_reclamado_status = ausente` bloquea
2. `acto_reclamado_status = dudoso` escala
3. `interes_status = ausente` bloquea
4. `interes_status = dudoso` escala
5. `definitividad_status = incumplida` bloquea
6. `definitividad_status = dudosa` escala
7. `suspension_status = inviable` bloquea
8. `suspension_status = delicada` escala
9. `proyecto_madurez = inviable` bloquea
10. `proyecto_madurez = inmaduro` escala

Subperfil `amparo_suspension`:

1. `abogado_quejoso`
2. `autoridad_responsable_revisor`
3. `secretario_proyectista_revisor`
4. `revisor_suspension_amparo`
5. `revisor_interes_social_orden_publico`
6. `revisor_jurisprudencial`

Controles materiales en `amparo_suspension`:

1. `apariencia_status = ausente` bloquea
2. `apariencia_status = debil` escala
3. `peligro_demora_status = ausente` bloquea
4. `peligro_demora_status = dudoso` escala
5. `medida_status = inviable` bloquea
6. `medida_status = estrecha` escala
7. `interes_social_status = afectado` bloquea
8. `interes_social_status = sensitivo` escala
9. `orden_publico_status = afectado` bloquea
10. `orden_publico_status = sensitivo` escala
11. `proyecto_cautelar_madurez = inviable` bloquea
12. `proyecto_cautelar_madurez = inmaduro` escala

La correccion importante es esta: `amparo_suspension` ya no es el perfil recomendado para operacion fina. Sirve como compatibilidad. La estrategia correcta ahora se divide asi:

1. `amparo_suspension_oficio`
2. `amparo_suspension_parte`

`amparo_suspension_oficio`:

1. `abogado_quejoso`
2. `autoridad_responsable_revisor`
3. `secretario_proyectista_revisor`
4. `revisor_suspension_oficio_amparo`
5. `revisor_interes_social_orden_publico`
6. `revisor_jurisprudencial`

Controles materiales en `amparo_suspension_oficio`:

1. `supuesto_oficio_status = ausente` bloquea
2. `supuesto_oficio_status = dudoso` escala
3. `riesgo_grave_status = ausente` bloquea
4. `riesgo_grave_status = insuficiente` escala
5. `medida_status = inviable` bloquea
6. `medida_status = estrecha` escala
7. `interes_social_status = afectado` bloquea
8. `interes_social_status = sensitivo` escala
9. `orden_publico_status = afectado` bloquea
10. `orden_publico_status = sensitivo` escala
11. `proyecto_cautelar_madurez = inviable` bloquea
12. `proyecto_cautelar_madurez = inmaduro` escala

`amparo_suspension_parte`:

1. `abogado_quejoso`
2. `autoridad_responsable_revisor`
3. `secretario_proyectista_revisor`
4. `revisor_suspension_parte_amparo`
5. `revisor_interes_social_orden_publico`
6. `revisor_jurisprudencial`

Controles materiales en `amparo_suspension_parte`:

1. `apariencia_status = ausente` bloquea
2. `apariencia_status = debil` escala
3. `peligro_demora_status = ausente` bloquea
4. `peligro_demora_status = dudoso` escala
5. `medida_status = inviable` bloquea
6. `medida_status = estrecha` escala
7. `garantia_status = omisa` bloquea
8. `garantia_status = delicada` escala
9. `interes_social_status = afectado` bloquea
10. `interes_social_status = sensitivo` escala
11. `orden_publico_status = afectado` bloquea
12. `orden_publico_status = sensitivo` escala
13. `proyecto_cautelar_madurez = inviable` bloquea
14. `proyecto_cautelar_madurez = inmaduro` escala

## Uso

```bash
python3 scripts/legal_panel_orchestrator.py --session fixtures/legal_panel_session_pass.json
python3 scripts/legal_panel_orchestrator.py --session fixtures/legal_panel_session_fail_vote_drift.json
python3 scripts/legal_panel_orchestrator.py --session fixtures/legal_panel_session_amparo_pass.json
python3 scripts/legal_panel_orchestrator.py --session fixtures/legal_panel_session_amparo_escalated_procedencia.json
python3 scripts/legal_panel_orchestrator.py --session fixtures/legal_panel_session_amparo_blocked_definitividad.json
python3 scripts/legal_panel_orchestrator.py --session fixtures/legal_panel_session_amparo_suspension_pass.json
python3 scripts/legal_panel_orchestrator.py --session fixtures/legal_panel_session_amparo_suspension_escalated.json
python3 scripts/legal_panel_orchestrator.py --session fixtures/legal_panel_session_amparo_suspension_blocked.json
python3 scripts/legal_panel_orchestrator.py --session fixtures/legal_panel_session_amparo_suspension_oficio_pass.json
python3 scripts/legal_panel_orchestrator.py --session fixtures/legal_panel_session_amparo_suspension_oficio_blocked.json
python3 scripts/legal_panel_orchestrator.py --session fixtures/legal_panel_session_amparo_suspension_parte_pass.json
python3 scripts/legal_panel_orchestrator.py --session fixtures/legal_panel_session_amparo_suspension_parte_escalated.json
```

## Salidas

Bundle candidato:

`raw/legal_panel/candidates/`

Recibos:

`raw/guardrails/receipts/legal_panel_receipts.jsonl`

## Límite honesto

Esto ya replica el patron fuerte de:

1. primera ronda sellada
2. reveal post-deliberacion
3. guardrail de drift
4. evidencia local con `merkle_root`
5. veto y escalacion por funcion juridica

Todavia no hace:

1. llamadas reales a Anthropic
2. llamadas reales a Ollama
3. anclaje externo tipo Evidence Bus
