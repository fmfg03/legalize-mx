# Expediente Backend

This backend is the first system-of-record scaffold for case-specific Mexican legal operations.

It is separate from the corpus pipeline already present in this repository.

## Why it exists

The repo already persists:

1. legal corpus documents
2. retrieval indexes
3. raw ingestion artifacts
4. guardrail receipts

But it did not have a backend for per-expediente operational data such as:

1. notificaciones
2. emplazamientos
3. acuerdos
4. sentencias
5. escritos
6. anexos
7. deadlines
8. actuaciones

## Stack

1. PostgreSQL
2. FastAPI
3. SQLAlchemy
4. Alembic
5. managed local file storage under `storage/expedientes/`

For local development, the backend now defaults to a repo-local SQLite database at:

`storage/expedientes/legalize_mx.db`

PostgreSQL remains the intended production store and can be enabled by setting:

`LEGALIZE_MX_DATABASE_URL`

## Current scope

The scaffold includes:

1. expediente records
2. parties
3. documents
4. document versions
5. events / actuaciones
6. deadlines
7. release receipts
8. users
9. API keys
10. append-only audit logs

## Layout

1. app entrypoint: `backend/app/main.py`
2. config: `backend/app/config.py`
3. DB wiring: `backend/app/db.py`
4. models: `backend/app/models/`
5. schemas: `backend/app/schemas/`
6. API routes: `backend/app/api/routes/`
7. migrations: `backend/alembic/`

## Document persistence model

Metadata lives in PostgreSQL.

Binary files live under:

`storage/expedientes/{expediente_id}/{document_id}/`

Each new file is stored as a document version with:

1. `version_number`
2. `file_name`
3. `mime_type`
4. `storage_key`
5. `sha256`
6. `size_bytes`
7. `source_kind`

## Initial API

1. `GET /healthz`
2. `GET /api/v1/auth/me`
3. `GET /api/v1/admin/users`
4. `POST /api/v1/admin/users`
5. `PATCH /api/v1/admin/users/{user_id}`
6. `POST /api/v1/admin/users/{user_id}/api-keys`
7. `GET /api/v1/admin/users/{user_id}/api-keys`
8. `PATCH /api/v1/admin/users/{user_id}/api-keys/{api_key_id}`
9. `GET /api/v1/admin/audit-logs`
10. `GET /api/v1/expedientes`
11. `POST /api/v1/expedientes`
12. `PATCH /api/v1/expedientes/{expediente_id}`
13. `GET /api/v1/expedientes/{expediente_id}`
14. `GET /api/v1/expedientes/{expediente_id}/audit-logs`
15. `GET /api/v1/expedientes/{expediente_id}/parties`
16. `POST /api/v1/expedientes/{expediente_id}/parties`
17. `PATCH /api/v1/expedientes/{expediente_id}/parties/{party_id}`
18. `GET /api/v1/expedientes/{expediente_id}/documents`
19. `POST /api/v1/expedientes/{expediente_id}/documents`
20. `GET /api/v1/expedientes/{expediente_id}/documents/{document_id}`
21. `PATCH /api/v1/expedientes/{expediente_id}/documents/{document_id}`
22. `POST /api/v1/expedientes/{expediente_id}/documents/{document_id}/versions`
23. `GET /api/v1/expedientes/{expediente_id}/documents/{document_id}/versions/{version_id}`
24. `GET /api/v1/expedientes/{expediente_id}/documents/{document_id}/versions/{version_id}/download`
25. `POST /api/v1/expedientes/{expediente_id}/documents/{document_id}/upload`
26. `POST /api/v1/expedientes/{expediente_id}/events`
27. `GET /api/v1/expedientes/{expediente_id}/deadlines`
28. `POST /api/v1/expedientes/{expediente_id}/deadlines`
29. `PATCH /api/v1/expedientes/{expediente_id}/deadlines/{deadline_id}`
30. `GET /api/v1/expedientes/{expediente_id}/release-receipts`
31. `POST /api/v1/expedientes/{expediente_id}/release-receipts`

`GET /api/v1/expedientes` already supports early filters:

1. `expediente_number`
2. `matter_type`
3. `jurisdiction_level`
4. `status`
5. `q`
6. `limit`

## Upload path

There are now two ways to create document versions:

1. JSON route with `content_base64`
2. multipart route with a real uploaded file

The multipart route is the better operator path:

`POST /api/v1/expedientes/{expediente_id}/documents/{document_id}/upload`

Form fields:

1. `source_kind`
2. `notes`
3. `extracted_text`
4. `created_by`
5. `mime_type`
6. `extra_json`
7. `file`

## Audit hint

Write routes now require API key authentication.

Supported headers:

1. `Authorization: Bearer <api_key>`
2. `X-API-Key: <api_key>`

`GET /api/v1/auth/me` resolves the current user from that key.

Every write now stores:

1. actor user ID on the affected record
2. append-only row in `audit_logs`

The `created_by` string on document versions is still available for document provenance labels, but the authoritative actor is `created_by_user_id`.

## Roles

The backend now uses four roles:

1. `observer`: read-only expediente access
2. `operator`: expediente, party, document, version, event, and deadline mutations
3. `reviewer`: release receipt creation and review actions
4. `admin`: user and API key lifecycle plus global audit access

The current admin user cannot deactivate itself through `PATCH /api/v1/admin/users/{user_id}`.

## Admin lifecycle

Admin routes now cover:

1. user creation
2. user role and active-state updates
3. per-user API key creation
4. per-user API key listing
5. API key deactivation and relabeling

## Audit filters

There are now two audit views:

1. `GET /api/v1/expedientes/{expediente_id}/audit-logs`
2. `GET /api/v1/admin/audit-logs`

Supported filters include:

1. `action`
2. `entity_type`
3. `actor_user_id`
4. `created_from`
5. `created_to`
6. `limit`

The global admin audit view also supports:

1. `expediente_id`
2. `entity_id`

## Run intent

Install dependencies first, then run migrations, then start the API:

```bash
python3 -m venv .venv
.venv/bin/pip install -e .
.venv/bin/python scripts/bootstrap_expediente_auth.py \
  --email admin@example.com \
  --name "Admin Legalize MX" \
  --role admin \
  --key-label local-admin
.venv/bin/uvicorn backend.app.main:app --reload
```

The bootstrap script prints the plaintext API key once. Use it in:

```bash
curl -H "Authorization: Bearer <api_key>" http://127.0.0.1:8000/api/v1/auth/me
```

If you stay on the default SQLite URL, the app auto-creates tables on startup.

If you switch to PostgreSQL, run migrations explicitly:

```bash
LEGALIZE_MX_DATABASE_URL='postgresql+psycopg://user:pass@localhost:5432/legalize_mx' \
  .venv/bin/alembic -c backend/alembic.ini upgrade head
```

## Important separation

This backend is for expediente operations.

It does not replace:

1. `mexico/`
2. `indexes/`
3. `raw/`

Those remain the corpus, ingestion, and guardrail layers.
