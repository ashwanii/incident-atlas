# Verification record

Date: 3 November 2026. Host test interpreter: Python 3.10.9, macOS-27.2-arm64-arm-64bit. Deployment target: Python 3.12 in Docker. Host tests do not prove the container image works.

| Check | Observed result |
|---|---|
| API/service regression suite | 19 passed; one Starlette/AnyIO deprecation warning |
| Synthetic task evaluation | 15/15 passed; local API p95 6.394 ms |
| Scale fixture | 3,000 short synthetic published RCA documents, direct fixture inserts |
| Scale requests | 200 GET requests, eight client threads, 100 ID / 100 lexical |
| Scale exact ID p95 / p99 | 54.3 / 63.776 ms |
| Scale lexical p95 / p99 | 89.95 / 93.971 ms |
| Synthetic benchmark top-1 | All 200 expected identities returned first |
| Coarse search latency gate | Both p95 values below 1,000 ms; passes |
| Model cost | 0 calls, 0 tokens, $0 model API spend per request |
| Online backup | Backup of live five-document sample database completed and integrity checked |
| JavaScript | `node --check app/static/app.js` passed |
| Compose | `docker compose config --quiet` passed with test environment keys |
| Container startup | Not executed: Docker daemon unavailable on this host |
| Browser | UI loaded; same-title RCA/SOP results separated; ambiguity visible; SOP source dialog and cited exact-order chat verified |
| TOML | No TOML files in application deliverable; application does not read TOML |

Raw evidence: `test-results.txt`, `evaluation-run.txt`, `benchmark-run.txt`, `../evaluation/results.json`, `../evaluation/benchmark-results.json`. `ui-preview.png` is a full-page capture of the actual responsive UI showing separate RCA/SOP results.

The regression suite includes 30 concurrent identical-source ingestions and 20 concurrent renamed exact-content sources from an empty database. It checks one identity/version/index row where appropriate and alias persistence after edits. It also checks that command case/indentation edits produce new versions, so deduplication cannot hide meaningful procedure changes.

The declared holdout was created before the first evaluator run, then inspected. It is now a regression set, not a still-sealed test set. The sample is too small for meaningful confidence intervals. Documents and queries are synthetic and share vocabulary. A perfect score here is not a claim about general incident understanding, synonym recall, real legacy-document quality or secret-detection recall.

Latency is local in-process TestClient latency, including telemetry writes and excluding real network/TLS/container overhead. The scale fixture deliberately bypasses ingestion to measure retrieval. It does not establish ingestion scalability or 400-user capacity. Hosting cost is not included in the zero model-cost figure. CI gates the suite, synthetic task cases and coarse synthetic search budget; deployment still needs real-corpus and load validation.
