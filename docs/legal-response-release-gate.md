# Legal Response Release Gate

El gate de jurisprudencia por si solo ya no basta. Si se deja como script opcional, alguien lo omite y el sistema vuelve a inventar o a citar autoridad no verificada live.

La ruta correcta es:

1. construir `assistant_response_bundle`
2. pasar el bundle por el gate de autoridad juridica
3. evaluar y liberar la versión persistida mediante el cliente autenticado `scripts/release_legal_response.py`
4. solo liberar al usuario si el resultado es `APPROVED`

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

Es cliente del servidor MCP autenticado. El servidor:

1. ejecuta el gate de autoridad juridica contra corpus local y resolvedores autorizados
2. ejecuta el grounding gate con indice local mas evidencia suplementaria verificable
3. persiste ejecución y evidencia de ambos gates vinculadas a actor, expediente, versión y bundle
4. determina `approved` o `blocked`; el recibo, auditoría y outbox se comprometen juntos

La CLI solo emite `APPROVED` después de recibir el recibo persistido que corresponde
a esa ejecución. No acepta verdict/actor/fixtures/políticas elegidos por cliente.

## Artefactos

GateExecution, ReleaseReceipt, auditoría y ReleaseOutbox residen en la base del
servidor. El worker exporta eventos comprometidos a
`storage_root/releases/outbox/{event_id}.json`, con escritura atómica e idempotente.
Los JSONL/archivos de los scripts históricos no se importan como evidencia de liberación.

## Uso

```bash
python3 scripts/release_legal_response.py \
  --bundle bundle.json \
  --expediente-id UUID_DEL_EXPEDIENTE \
  --document-version-id UUID_DE_LA_VERSION \
  --mcp-url https://servidor.example/mcp
```

Requiere un bearer de sesión existente en `LEGALIZE_MX_SESSION_BEARER`, usuario y
binding activos, scopes legalize:read/legalize:release y rol reviewer/admin.
response_text debe coincidir con la extracción servidor de los bytes de esa versión.
Sin contexto autenticado, IDs persistidos o evidencia válida falla cerrado. No hay
alta automática ni IdP nuevo. MCP está deshabilitado por defecto; habilitarlo en un
entorno real requiere un alcance de configuración autorizado por separado.

Contrato, pruebas y límites semánticos/de formato:
[slice0-local-validation.md](slice0-local-validation.md).
Estado de publicación: [slice0-publication-checkpoint.md](slice0-publication-checkpoint.md).

## Regla operativa

Un escrito juridico no sale por `response_text` crudo.

Sale solo si existe:

1. bundle estructurado
2. recibo de grounding
3. recibo de liberacion con `release_verdict = APPROVED`
