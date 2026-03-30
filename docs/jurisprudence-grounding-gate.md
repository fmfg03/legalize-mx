# Jurisprudence Grounding Gate

Este gate existe para bloquear una clase concreta de error: que el asistente afirme tesis, precedentes o jurisprudencia que no estan en el indice local verificable.

No depende de prompt. Depende de evidencia.

## Idea

El patron viene de dos piezas que ya existen en `zaubern`:

1. `tools/claims-language-gate.mjs`: politica declarativa para detectar lenguaje prohibido
2. `techfile/evidence/slice_verify.py`: recibo verificable con resumen de checks

Aqui se adapto ese patron a derecho mexicano.

## Regla operacional

Una salida juridica falla si ocurre cualquiera de estas condiciones:

1. menciona jurisprudencia, tesis, precedentes, SCJN o SJF y no trae cita jurisprudencial verificada
2. una cita jurisprudencial no coincide con el indice local `indexes/jurisprudence_chunks.jsonl`
3. una cita jurisprudencial trae `quote` pero la cita no coincide con su `quote_sha256`
4. una `quote` jurisprudencial no aparece en el texto del chunk local
5. un claim marcado como `jurisprudence` o `mixed` no tiene al menos una cita jurisprudencial verificada

## Bundle de entrada

Schema:

`schemas/assistant_response_bundle.schema.json`

Campos minimos:

1. `response_text`
2. `citations`
3. `claims`

## Politica

`config/jurisprudence_grounding_policy.json`

La politica define:

1. patrones de lenguaje que no pueden aparecer sin evidencia
2. tipos de claim que exigen sustento jurisprudencial
3. si se exige `quote` y coincidencia local

## Comando

```bash
python3 scripts/validate_jurisprudence_grounding.py \
  --bundle fixtures/assistant_response_pass_no_jurisprudence.json
```

Caso que debe fallar:

```bash
python3 scripts/validate_jurisprudence_grounding.py \
  --bundle fixtures/assistant_response_fail_fake_jurisprudence.json
```

## Recibo

Por defecto el gate anexa un recibo JSONL en:

`raw/guardrails/receipts/jurisprudence_grounding_gate_receipts.jsonl`

Ese recibo no vuelve verdadera a la salida. Solo deja auditable:

1. que bundle se valido
2. que politica se aplico
3. que checks pasaron o fallaron
4. por que se bloqueo la respuesta
