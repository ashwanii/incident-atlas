# Assignment requirement map

| Requirement | Running implementation / evidence | Remaining limit |
|---|---|---|
| Identity/type/currentness | Stable IDs, source aliases, versions, owner/service/review metadata, review reasons | Rule confidence is uncalibrated |
| Brownfield ingestion | TXT/MD/text PDF, structure classification, deduplication, review queue | No OCR; manual curator split for mixed sources |
| Repeated/concurrent/edited/deleted correctness | Atomic document/version/index updates; 30 repeated and 20 renamed concurrent tests | Source revisions are last-committed-write; no automatic connector reconciliation |
| Exact document retrieval | ID and quoted-title routes never fall through; ambiguity exposed | No universal natural-language exact-title resolver |
| Live issue suggestions | Separate RCA/SOP ranks with matching-token explanations and abstention | Lexical recall, limited noise normalization; no semantic model |
| Chat grounding and procedure order | Complete redacted excerpts, version citations, type checks, session pointers | No generated synthesis; source correctness still needs owner approval |
| Intent understanding | Rules, clarification, context and topic switch tests | Mixed/poor wording is a known weakness to evaluate on real queries |
| Quality measurement | Declared development/holdout, per-origin/task summaries, raw outputs, CI | Tiny synthetic sample; fresh sealed real-corpus set required |
| Latency and cost | Per-request headers/logs, raw timings, synthetic scale benchmark, zero model spend | No network/400-user SLO proof; hosting cost separate |
| Operations | Safe errors, health, transaction consistency, redaction, bounded extraction, metrics, backup tool | SSO/ACLs, HA, full DLP, encrypted backups, rate limits and source connectors remain production work |
| Deliverables | Source, Docker command, UI, README, run guide, design, report, tests, isolation evidence, evaluation outputs, cuts | No private remote repository created or published |

The “isolation evidence” wording is ambiguous in the supplied brief. This repository documents RCA/SOP and reader/curator isolation explicitly; it does not imply tenant isolation.
