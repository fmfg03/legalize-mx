# Operacion

## Ejecucion manual de un ciclo

```bash
/root/legalize-mx/.venv/bin/python /root/legalize-mx/scripts/run_ingestion_cycle.py \
  --source-ids-file /root/legalize-mx/ops/ingestion/source_ids.txt \
  --resume-from-log \
  --retry-partials \
  --allow-partial \
  --drain-queue
```

## Ejecucion manual de un ciclo jurisprudencial

```bash
/root/legalize-mx/.venv/bin/python /root/legalize-mx/scripts/run_scjn_jurisprudence_cycle.py \
  --all-kinds \
  --page-size 10 \
  --pages-per-run 1
```

## Instalacion de systemd

Copiar las unidades versionadas a `/etc/systemd/system/`:

```bash
sudo cp /root/legalize-mx/ops/systemd/legalize-mx-ingestion.service /etc/systemd/system/
sudo cp /root/legalize-mx/ops/systemd/legalize-mx-ingestion.timer /etc/systemd/system/
sudo cp /root/legalize-mx/ops/systemd/legalize-mx-jurisprudence.service /etc/systemd/system/
sudo cp /root/legalize-mx/ops/systemd/legalize-mx-jurisprudence.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now legalize-mx-ingestion.timer
sudo systemctl enable --now legalize-mx-jurisprudence.timer
```

## Verificacion

```bash
systemctl status legalize-mx-ingestion.timer
systemctl list-timers --all | grep legalize-mx-ingestion
journalctl -u legalize-mx-ingestion.service -n 50 --no-pager
systemctl status legalize-mx-jurisprudence.timer
systemctl list-timers --all | grep legalize-mx-jurisprudence
journalctl -u legalize-mx-jurisprudence.service -n 50 --no-pager
```

## Artefactos operativos

1. log por norma: `raw/diputados/logs/ingestion_log.jsonl`
2. snapshots por lote: `raw/diputados/logs/batch_runs/`
3. cola de pendientes: `raw/diputados/queue/pending_downloads.jsonl`
4. cache persistente: `raw/diputados/cache/`
5. estado jurisprudencial por tipo: `raw/scjn/state/*_batch_state.json`
6. snapshots jurisprudenciales por lote: `raw/scjn/logs/batch_runs/`
7. snapshots crudos jurisprudenciales: `raw/scjn/snapshots/*.jsonl`
