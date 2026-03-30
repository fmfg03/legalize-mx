# Legal Response Release Gate

El gate de jurisprudencia por si solo no basta. Si se deja como script opcional, alguien lo omite y el sistema vuelve a inventar.

La ruta correcta es:

1. construir `assistant_response_bundle`
2. pasar el bundle por `scripts/release_legal_response.py`
3. solo liberar al usuario si el resultado es `APPROVED`

## Politica

`config/legal_response_release_policy.json`

Protege salidas como:

1. `demand`
2. `petition`
3. `brief`
4. `recommendation`
5. `conclusion`
6. `legal_opinion`

## Script

`scripts/release_legal_response.py`

Hace tres cosas:

1. ejecuta el gate jurisprudencial con el indice local
2. persiste el recibo del gate
3. emite un recibo de liberacion y clasifica el bundle como `approved` o `blocked`

## Artefactos

Recibos del gate:

`raw/guardrails/receipts/jurisprudence_grounding_gate_receipts.jsonl`

Recibos de liberacion:

`raw/guardrails/receipts/legal_response_release_receipts.jsonl`

Bundles liberados o bloqueados:

`raw/guardrails/releases/approved/`

`raw/guardrails/releases/blocked/`

## Uso

```bash
python3 scripts/release_legal_response.py --bundle fixtures/assistant_response_pass_no_jurisprudence.json
python3 scripts/release_legal_response.py --bundle fixtures/assistant_response_fail_fake_jurisprudence.json
```

## Regla operativa

Un escrito juridico no sale por `response_text` crudo.

Sale solo si existe:

1. bundle estructurado
2. recibo de grounding
3. recibo de liberacion con `release_verdict = APPROVED`
