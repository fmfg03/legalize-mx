# Operator Console

Internal console for operating the `legalize-mx` repository as a data system.

It is intentionally narrow. It does not try to be a public assistant UI.

## What it shows

1. corpus counts from `mexico/` and `indexes/`
2. latest federal legislation ingestion health
3. latest SCJN jurisprudence ingestion health
4. pending Diputados queue pressure
5. guardrail and release receipts
6. newest canonical documents written to disk

## Run

```bash
python3 scripts/run_operator_console.py --host 127.0.0.1 --port 4173
```

Then open:

`http://127.0.0.1:4173`

## Implementation

1. server: `scripts/run_operator_console.py`
2. UI shell: `ops/console/index.html`
3. UI logic: `ops/console/app.js`
4. UI styling: `ops/console/styles.css`

## Design intent

The first UI layer is an operator surface, not a chatbot.

That is deliberate. This repo already has:

1. ingestion machinery
2. canonical corpora
3. retrieval indexes
4. release guardrails

The immediate need is visibility into those systems, not a polished end-user shell on top of unstable internals.
