# How to run Incident Atlas

## 1. Docker (recommended)

Install Docker with the Compose plugin and start the Docker daemon. From the extracted project folder:

```sh
sh scripts/bootstrap.sh
```

Open http://localhost:8000. Read `.env` locally; use `API_KEY` for reader access or `ADMIN_KEY` for curator actions. Those are two different random values. Do not paste keys into chat, screenshots or source control. If you supply an existing `.env`, it must define both keys with distinct, nonempty values.

The script uses Python 3 only to create keys. To configure without Python, copy `.env.example` to `.env`, replace both placeholders with different strong random secrets, and run:

```sh
docker compose up --build -d
```

Health and logs:

```sh
curl http://localhost:8000/health/ready
docker compose ps
docker compose logs --tail=100 atlas
```

The Compose binding is localhost only. For shared hosting, use an authenticated TLS reverse proxy with request/query logging disabled or redacted. Never expose this development HTTP endpoint directly to the internet.

## 2. Local Python alternative

Python 3.12 is the deployment target; tests were also exercised on the host version recorded in `docs/VERIFICATION.md`.

```sh
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements-lock.txt
export API_KEY="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')"
export ADMIN_KEY="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')"
export DATA_DIR=./data
uvicorn app.main:app --host 127.0.0.1 --port 8000 --no-access-log
```

Keep that terminal open. Set the same key values in another terminal for API and seeding commands. Local data defaults to `data/atlas.sqlite3`. Do not put it on a shared/network filesystem.

`requirements.txt` lists pinned direct dependencies. `requirements-lock.txt` additionally pins transitive versions captured during verification. Neither uses TOML. Python package dependencies may internally support TOML; this application never reads or requires a TOML configuration.

## 3. Load sample documents

With local Python dependencies installed, set `ADMIN_KEY` to the curator key used by the running server:

```sh
python scripts/seed.py
```

For Docker users, create a local virtual environment as above for the seed script. Alternatively paste sample documents from `examples/documents.json` into the UI. There is no automatic sample loading in production. The seed is repeatable. Expected: Kafka RCA, Kafka SOP and Redis RCA are published; the mixed Kafka source and unknown legacy note enter review.

## 4. Walk through the UI

1. Enter the reader key. In Discover, search `Kafka consumer lag`. Both identically titled documents appear in separate RCA and SOP columns. The ambiguity notice requires selection.
2. Search a returned `DOC-...` ID. You get only that identity. Search `DOC-NONEXISTENT` and get no results.
3. Paste `kafka consumer lag` and choose **Suggest for live issue**. Read the match explanation and freshness metadata.
4. Open the SOP and choose **Discuss this document**. Ask `how to handle kafka lag`. The complete procedure appears with a version citation.
5. Start a fresh conversation, ask `why kafka consumer lag`, then `and impact?`, then `how to handle kafka consumer lag`. Observe the topic switch.
6. Enter the curator key, add legacy text or upload a file, and inspect the returned status/reasons. Refresh the review queue. Mixed or unsafe procedures cannot be approved until edited and re-ingested.
7. Edit using the exact same source key to create a new version under the same ID. UI uploads are brownfield; use structured text ingestion for greenfield metadata.

## 5. API examples

The shell variable `API_KEY` below contains a reader key; use `ADMIN_KEY` for mutation endpoints.

```sh
curl -H "X-API-Key: $API_KEY" 'http://localhost:8000/api/search?q=kafka&kind=RCA'
curl -H "X-API-Key: $API_KEY" 'http://localhost:8000/api/suggest?q=redis%20memory%20exhaustion'
curl -H "X-API-Key: $API_KEY" -H 'Content-Type: application/json' \
  -d '{"message":"why did kafka consumer lag increase"}' http://localhost:8000/api/chat
curl -H "X-API-Key: $ADMIN_KEY" -H 'Content-Type: application/json' \
  --data-binary @examples/single-document.json http://localhost:8000/api/documents
curl -H "X-API-Key: $ADMIN_KEY" \
  -F source_key=legacy/runbook -F title='Legacy runbook' -F services=kafka \
  -F file=@examples/runbook.md http://localhost:8000/api/uploads
curl -H "X-API-Key: $ADMIN_KEY" http://localhost:8000/api/metrics
```

Copy `session_id` from a successful chat response and send it in the next request to keep context. To select an ambiguous document, send its `document_id`. Sessions expire after 24 hours and are shared within the reader trust scope; opaque IDs are not per-user authorization.

## 6. Tests and evaluation

```sh
python -m pytest -q
python -m evaluation.run
python -m evaluation.benchmark
```

The evaluator creates an isolated temporary database; it does not change the running application. It writes `evaluation/results.json`, including each expected/actual answer, origin, split, latency and model cost. The development and holdout labels were declared before the first evaluator run. Once inspected, the holdout must be replaced with a fresh labeled set for future tuning.

## 7. Backup and recovery

Use SQLite's online backup API, not a copy of the main database while WAL is active:

```sh
python scripts/backup.py data/atlas.sqlite3 backups/atlas.sqlite3
```

For Docker, use a maintenance container or stop the service before exporting the complete data volume. A live volume export is not a guaranteed consistent SQLite backup. Backups contain redacted operational data and historical versions; encrypt them and restrict access. Test restoration into a separate environment. Restart with the restored database in `DATA_DIR` and check readiness, exact document retrieval and version numbers.

Stop with `docker compose down`; data remains. `docker compose down -v` deliberately destroys the volume and all documents. Do not use `-v` for a normal shutdown.

## Troubleshooting

| Symptom | Resolution |
|---|---|
| Cannot connect to Docker daemon | Start Docker Desktop/Engine, then repeat bootstrap. |
| Startup rejects keys | Set distinct nonempty reader/curator keys and recreate the container. |
| 401 / 403 | Reader key is missing/incorrect, or a curator operation needs the curator key. |
| 413 | Reduce upload to 2 MiB; request envelope also has a limit. |
| 415 / 422 file error | Use UTF-8 TXT/MD or an unencrypted text PDF, at most 40 pages. Scan-only PDFs need external OCR. |
| 409 review conflict | Edit/split unsafe or mixed content and re-ingest with its original source key. |
| 503 storage unavailable | Inspect disk space, local volume permissions and lock pressure; retry after the indicated delay. |
| No result | Document may be quarantined/deleted, or lexical evidence is insufficient. Try an exact ID, service or error. |
| No FTS5 module | Use the supplied Python Docker image or a Python build whose SQLite supports FTS5. |
| PDF parser timeout | Convert the PDF to vetted UTF-8 text offline; parser timeout is intentionally bounded. |
