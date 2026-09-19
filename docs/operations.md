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

## Despliegue web de Lexera

Servicios versionados:

1. `ops/systemd/lexera-api.service`
2. `ops/systemd/lexera-console.service`
3. `ops/nginx/lexera.mx`
4. `ops/systemd/lexera-console.env.example`

Instalacion basica:

```bash
sudo mkdir -p /var/www/letsencrypt
sudo cp /root/legalize-mx/ops/systemd/lexera-api.service /etc/systemd/system/
sudo cp /root/legalize-mx/ops/systemd/lexera-console.service /etc/systemd/system/
sudo cp /root/legalize-mx/ops/nginx/lexera.mx /etc/nginx/sites-available/lexera.mx
sudo ln -s /etc/nginx/sites-available/lexera.mx /etc/nginx/sites-enabled/lexera.mx
sudo systemctl daemon-reload
sudo systemctl enable --now lexera-api.service
sudo systemctl enable --now lexera-console.service
sudo nginx -t
sudo systemctl reload nginx
```

Emision de certificados:

```bash
sudo certbot --nginx -d lexera.mx -d www.lexera.mx -d api.lexera.mx
```

En Cloudflare, usar `Full (strict)` despues de que el certificado del origen quede instalado.

El servicio web de Lexera ahora necesita variables internas para hablar con el backend y con Ollama:

```bash
sudo cp /root/legalize-mx/ops/systemd/lexera-console.env.example /etc/default/lexera-console
sudo nano /etc/default/lexera-console
sudo systemctl daemon-reload
sudo systemctl restart lexera-console.service
```

Variables:

1. `LEXERA_API_BASE_URL`
2. `LEXERA_API_KEY`
3. `LEXERA_OLLAMA_CHAT_URL`
4. `LEXERA_OLLAMA_MODEL`

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
