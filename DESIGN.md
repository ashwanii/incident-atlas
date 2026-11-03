# Design and production plan

## 1. Problem and safety boundary

The assignment describes roughly 400 engineers and several thousand RCA/SOP documents. It is a knowledge retrieval system, not an autonomous remediation agent. RCA describes what happened; SOP describes what to do. A procedure must retain its authoritative sequence, prerequisites and rollback. Availability without correctness is dangerous here.

The implemented trust boundary is one organization with two shared roles. All published documents are readable by all holders of the reader key. Curators can inspect quarantined data and mutate documents. This is **not tenant isolation**. The RCA/SOP isolation claim means type-scoped retrieval, citations and selected-document checks; `docs/ISOLATION.md` gives evidence and limits.

## 2. Implemented architecture

FastAPI serves both the JSON API and a static, same-origin browser UI. Synchronous database work uses FastAPI worker threads; upload extraction is explicitly sent to the thread pool. PDF parsing runs in a separate process with a 10-second timeout; Linux additionally enforces CPU and address-space limits. There are no remote retrieval/model dependencies. A single SQLite WAL database stores current documents, versions, aliases, sessions, audit events and recent telemetry. FTS5 indexes only published current documents.

Deployment is one non-root container and a named local volume. This is economical for the reference workload and avoids eventual consistency between a vector store and metadata database. SQLite still has one writer at a time. It is not suitable for cross-node writes or highly available storage. The operational production topology appears in section 11.

## 3. Data model and invariants

| Entity | Key and purpose |
|---|---|
| documents | Stable `DOC-...` primary key; unique canonical source key; current redacted content, type, services, owner, review date, status, heuristic confidence, reasons, digest, version, deletion flag |
| aliases | Unique source key mapped to canonical document ID after exact-content deduplication |
| versions | `(document_id, version)`; immutable redacted ingestion snapshot |
| search_index | One FTS row per active published document, no historical versions |
| sessions | Opaque ID, active kind and document ID, last interaction; 24-hour expiry |
| audit | Document ID, mutation action and UTC time; no source body |
| telemetry | Route template, status, elapsed milliseconds and time; latest 10,000 requests |

A source key identifies an upstream object, not an upload filename or title. Identical content under another name becomes an alias. Edits through that alias update the canonical identity. Metadata-only edits also increment the version. A `BEGIN IMMEDIATE` transaction serializes lookup/deduplication/write/index changes, so two simultaneous ingestions cannot both invent a new identity. The transaction is rolled back on any failure. There is no race-prone check followed by an independent commit.

Deletion soft-deletes the current row, removes its index row and removes session pointers in the same transaction. New requests no longer retrieve it. Historical versions remain for operator retention; there is no history endpoint. This is not cryptographic erasure. Responses already in flight cannot be retracted. Re-ingesting the same source explicitly revives the same ID with a new version.

If an edit collides with a different existing identity, return 409 rather than silently merge identity histories. Exact-content deduplication intentionally ignores metadata; conflicting owners/service declarations must be reconciled by a curator. This is a conservative reference policy, not a universal business rule.

## 4. Greenfield and brownfield ingestion

Greenfield requires declared type, owner, service and review date, and passes the same structural checks as legacy input. Brownfield TXT/MD/PDF is extracted without requiring manual rewriting. The supplied filename never controls a disk path. Raw uploads exist only in memory or anonymous parser pipes and are not persisted by application code. The multipart framework may spool larger uploads to private temporary files; those handles close in `finally`, with `/tmp` bounded to tmpfs in Docker.

Redaction runs before hashing, history storage, indexing and responses. It recognizes common credential assignments, bearer tokens, AWS key IDs, private key blocks, private IPv4 addresses and common internal-host suffixes. Source keys must be opaque identifiers, never secrets or signed URLs. Pattern redaction misses unknown secret formats; platform DLP and secret scanning are required before broad deployment. Redaction can change an executable command, so detected redactions also force review.

Structural signals include RCA root cause/impact/timeline/corrective actions and SOP prerequisites/steps/verification/rollback. Both strong signal families mean mixed content. Low evidence, declared-type conflicts, incomplete procedures, and skipped/duplicate step numbers enter review. A type in the review queue is provisional. Confidence values 0.45/0.90 are transparent heuristic labels, not measured probabilities.

Exact duplicates use a line-ending-normalized SHA-256 digest of redacted content. Case and indentation are preserved because commands can depend on both. Near duplicates use SequenceMatcher on the first 12,000 characters with a 0.88 threshold and are quarantined. This is intentionally conservative and O(N), can miss restructured or long-tail duplicates and has false positives. It is a baseline to replace with indexed MinHash/embedding candidates after evaluation. Mixed documents are retained intact but excluded from engineer retrieval. Curators split them into separate explicit RCA and SOP sources; automatic splitting was cut because unreliable boundaries can remove prerequisites.

## 5. Retrieval and noisy live issues

Search precedence: stable ID, exact title (including quoted exact title), then sanitized token-based FTS5. Missing IDs and quoted titles never fall back to a lookalike. Exact shared titles expose all matches and ambiguity. Optional kind filters are applied before results are returned.

Lexical candidates use FTS5 BM25 to shortlist up to 50 rows; title/service fields receive more candidate weight. A deduplicated query-token coverage score ranks the shortlist; coverage under 0.22 abstains. Up to 10 results are returned. Each explanation lists matching terms. Adjacent top scores within 0.15 expose ambiguity instead of silently selecting a chat source. These are visible development heuristics, not calibrated relevance probabilities.

Repeated stacktrace tokens are deduplicated and stopwords are removed. At most 64 distinct tokens contribute. This protects against repeated noisy lines, not arbitrary adversarial noise. The current lexical baseline misses synonym-only descriptions and truncates long unique traces. Noisy-input quality needs real alert/stacktrace evaluation. Suggestions independently query RCA and SOP indexes through kind filtering and return separate arrays, never a blended procedure/history list. Results return as a normal response; there is no artificial streaming delay.

## 6. Conversation and procedure safety

Intent rules identify incident-analysis versus procedural words. Mixed intent asks the engineer to choose RCA/SOP. A previous topic supplies context only when no new explicit intent is detected. The client can also specify kind. Selected documents must match the resolved kind or the server rejects the request.

Sessions persist only the topic and document pointer, not user questions or generated transcripts. Follow-ups re-read the current authoritative document; version edits therefore cannot leave cached old procedure text. Generic contextual phrases may retain the selected source. New explicit identities always take precedence. Expiry is checked on access, and expired rows are pruned during successful chats.

The answer is the entire redacted source document with ID/version/title citation. This supports faithful inspection, not concise generated Q&A. It never asserts an inferred root cause or rewrites an instruction. A citation means the excerpt is from that document, not that the document itself is correct. A stale review date (>180 days or unknown) is visible. Redacted SOPs need curator validation before publication. If the supporting source is absent, uncertain or ambiguous, the system abstains or requests selection.

## 7. Errors and degraded service

| Failure | Behavior |
|---|---|
| Invalid metadata | 422; safe field errors without echoing the submitted body |
| Missing/incorrect role key | 401 reader / 403 curator |
| Oversized/unsupported upload | 413 / 415; close upload handles |
| Corrupt, encrypted, scanned or excessive PDF | 422; parser subprocess terminates on timeout |
| Mixed/structurally unsafe review approval | 409; edit source first |
| Missing/deleted/unpublished document | 404; never substitute another identity |
| Storage unavailable or lock timeout | 503 with Retry-After; no stale fabricated answer |
| Telemetry unavailable | Continue serving successful operation; emit safe warning |
| Unexpected error | Generic 500 with correlation ID; log exception class, not body |

Because there are no remote model services, the application is already in its low-cost extractive fallback mode. If storage fails, UI/static assets and liveness still work but knowledge operations cannot. There is no claim that knowledge can be answered without its authoritative store. Parser failure affects the upload, not existing search. Production adds ingress rate/connection limits; application-level shared rate limiting is not implemented.

## 8. Cost and observability

Completed routed API responses include `X-Request-ID`, `X-Latency-Ms`, `X-LLM-Cost-USD: 0`. Template-route request logs avoid URL queries, payloads and credentials. Uvicorn access logging is disabled in the supplied deployment because query URLs can contain sensitive text. Operators must apply the same rule at ingress/load balancers.

`/api/metrics` reports recent per-route request count, mean latency and 5xx count plus model calls/tokens/cost (all zero). Telemetry is capped at 10,000 requests. The evaluator writes each request's measured wall time and zero model spend. Header latency excludes subsequent telemetry persistence and network transit; evaluator wall time includes the in-process HTTP request. Do not confuse them. Host CPU, storage and operations costs are not zero. Estimate hosting cost/request as monthly attributable infrastructure spend divided by monthly requests; log real billing rather than inventing a dollar value. Production metrics need histograms, p95/p99, disk space, lock time, queue depth and alerting via an external monitor.

## 9. Evaluation and release gates

The brief supplies no separate query dataset, so this repository creates its own declared development/holdout cases. `evaluation/cases.json` records origin, request task, expected behavior and split. `evaluation/run.py` seeds a temporary corpus and emits all raw results. Intent, search, suggestions and chat are separated; greenfield and brownfield appear separately in grouped summaries. There are not enough examples per cell for credible accuracy estimates. A perfect tiny score is only a smoke test.

Tests separately verify concurrent and repeated ingestion, alias edits, type isolation, exact procedure order, missing-ID abstention, ambiguity, review gates, stale-context deletion, metadata edits, malformed files, role controls and safe outages. CI blocks merge on any test/evaluation failure. It also runs the 3,000-document synthetic retrieval benchmark with a coarse 1-second p95 search budget. This catches gross slowdowns, not real-corpus quality regressions or small performance regressions. For production, create expert-labeled development/validation/sealed-test sets split by incident family and source (avoid near-duplicate leakage). Measure top-1 exact lookup, recall@5, MRR, selective precision/coverage, ambiguity accuracy, macro-F1 intent, exact SOP text/order, grounded-answer support and redaction recall. Report bootstrap confidence intervals and separately inspect unsafe false positives. Release requires no isolation/order failure and validated non-inferiority on the sealed test set, plus search p95 <1s and suggestion p95 <3s under the intended concurrent load.

## 10. Security and operational limits

The reference uses shared reader/curator keys, constant-time comparison, same-origin UI, no CORS enablement, restrictive CSP and safe text rendering with textContent. It cannot attribute actions to an individual and does not provide per-document authorization. Session IDs are opaque but exist within the common reader trust scope. Browser memory-only keys avoid persisted browser credentials; TLS is still mandatory outside local development. Uploaded documents are data; no content is executed, fetched as a URL or used as model instructions.

Database encryption at rest, backup encryption, key rotation, SSO/OIDC, per-service ACL filtering, audit retention, DLP coverage, disaster recovery, continuous dependency scanning and signed images are production prerequisites. Dependency pins provide repeatability, not a security guarantee. Use bounded retry with jitter on 503 only for idempotent operations; source-key ingestion is idempotent but concurrent different edits currently follow last-committed-write order. Add optimistic source revision checks for connectors.

## 11. Target topology beyond the reference

For shared production adoption: TLS ingress + OIDC -> stateless FastAPI replicas -> PostgreSQL authoritative metadata/version/ACL store; object storage only for vetted/encrypted originals when retention is required. Durable ingestion workers perform scanning/extraction and emit an outbox event in the metadata transaction. Search consumers apply monotonically increasing document versions and deletion tombstones. Search results must be re-authorized and checked against current DB versions before returning; index lag must never resurrect a deleted/restricted source. A unique `(connector, upstream_id)` plus digest constraints gives idempotence across workers.

Add local embeddings or a small bounded reranker only when a held-out corpus demonstrates sufficient recall gain over lexical search. Hybrid lexical/vector retrieval uses type and ACL filters before candidates and an evidence threshold calibrated on negatives. Cache embeddings by redacted digest; embed only changed documents; never use generated SOP steps. If RCA synthesis uses an LLM later, cap input tokens, retrieve few sections, enforce versioned citations, set deadlines/budget, and fall back to current extractive mode on timeout. Meter real vendor usage per request. This is a proposed extension, not hidden code in this submission.

## 12. References

- FastAPI's official container guidance: https://fastapi.tiangolo.com/deployment/docker/
- SQLite FTS5 reference: https://www.sqlite.org/fts5.html
- SQLite WAL concurrency and local-filesystem constraints: https://sqlite.org/wal.html

The separate [REPORT.md](REPORT.md) explains the implementation in presentation-friendly language. [CUTS.md](CUTS.md) lists deliberate omissions and next steps.
