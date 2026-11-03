# Implementation report: RCA and SOP knowledge system

## What was built

Incident Atlas is a browser-based operational knowledge application with a FastAPI backend. An engineer can add documents, find a specific document, get suggestions for a live issue and ask follow-up questions. Incident histories (RCAs) and operating procedures (SOPs) have separate labels, results and conversation topics.

The central design idea is to make the source dependable before making the answer fluent. For an on-call engineer, a confidently worded answer from the wrong procedure is worse than an explicit request to choose the correct source.

## Explain it to another person in two minutes

“An RCA tells us what went wrong in a previous incident. An SOP tells us the approved steps to follow. These often have the same title, so our system keeps their identities and types separate.

When a document arrives, we extract its text, redact recognizable secrets, identify its structure and check whether it already exists. If it is an edited source, it becomes a new version under the same ID. If it is a duplicate, it reuses the existing identity. If it is unclear, mixed or unsafe to interpret, it goes to a review queue.

When an engineer searches by ID, we either return that exact ID or say it is unavailable. We never substitute a lookalike. For incident descriptions, we find keyword evidence and explain which words matched, with RCAs and SOPs ranked separately.

For chat, we show the complete supporting source with a version citation. Procedures retain the source's exact sequence. There are no model calls in this version, which controls cost and avoids invented steps. The tradeoff is less semantic understanding and no concise generated answer.

The application runs in one Docker container, retains data in a volume, has a usable UI and includes tests, evaluation scripts and documentation. Enterprise identity, semantic retrieval and high availability are explicitly planned rather than claimed as completed.”

## How the implementation works, and why

### 1. A document's identity survives title changes

The source key is like a stable file number in a registry. The title is only a display name. A document also has a system-generated stable ID and a version counter. Editing the same source increments the counter. Re-uploading unchanged content does nothing. Uploading exact content under another name creates an alias to the same identity.

Why this matters: an engineer should not see five “different” runbooks when they are copies of one source. The duplicate lookup and write occur inside one database transaction, so simultaneous uploads do not create parallel identities.

### 2. Legacy content gets a first-class review path

The application supports pasted text and text-based PDFs/Markdown/TXT files. It looks for structural evidence rather than trusting the title. A source with both incident-analysis sections and procedural sections is treated as mixed. A one-line note without enough evidence is uncertain. Both are kept out of normal results until a curator resolves them.

Why this matters: forcing a definite classification onto messy historical material would hide uncertainty. Automatic bulk rewriting or splitting can accidentally detach rollback and prerequisites from the steps they constrain. This version deliberately asks a curator to split mixed sources.

### 3. Procedures stay intact

A chat question routes to RCA or SOP material. The answer is an exact full-body source excerpt after any required security redaction, with the source ID, title and version. The system never turns an SOP into a newly generated numbered list. It checks for consecutive source step numbers before publication.

Why this matters: instruction order is a safety property, not a writing preference. Source fidelity is measurable with exact text comparisons. It is still necessary for an owner to verify that the original procedure itself is correct.

### 4. Cost is controlled by architecture

Full-text search and intent rules run locally. There is no vector database or hosted generation call. Each request therefore has zero model tokens and zero model API spend. Hosting, storage and operations still need a real budget.

Why this matters: “cost optimized” should describe the entire system, not just a smaller prompt. For several thousand documents, a simple baseline is easier to measure and maintain. The design explains when local embeddings or bounded RCA synthesis would be justified by measured improvements.

### 5. Failures have explicit behavior

Malformed files, excessive uploads, missing documents, unauthorized operations, unsafe review approval and database failures have distinct HTTP error responses. Upload handles close even on failure. PDFs are parsed in a separate process with a timeout and Linux resource limits. Secret-like content is redacted before storage, but recognizable redactions also trigger review because a command may have changed.

Why this matters: an outage tool must fail visibly and safely. A storage failure does not cause the system to invent a replacement answer. A metrics-write failure does not unnecessarily stop a successful knowledge request.

## What has been verified

The repository includes executable tests and actual outputs in `docs/test-results.txt`, `evaluation/results.json` and `docs/VERIFICATION.md`. Tests cover repeat and concurrent ingestion, exact duplicate aliases, edit/version behavior, deletion, review gating, RCA/SOP isolation, source-faithful procedures, context changes, abstention, file rejection and role restrictions.

The synthetic evaluator separates development from declared holdout cases and reports greenfield/brownfield and request-task results. It is a small smoke test, not convincing evidence of production accuracy. The held-out cases have now been inspected and should be replaced before further tuning. No additional assignment query dataset was provided.

## What “production grade” means here

The delivered implementation uses production-oriented patterns: explicit boundaries, validated contracts, atomic state changes, safe error responses, resource limits, persistent storage, access roles, a hardened container and automated regression checks. It is a complete runnable reference, not a certified enterprise deployment.

Before serving all 400 engineers, the organization needs per-user SSO and service/document permissions, validated secret scanning, encrypted backups, a restore exercise, real-corpus relevance tests and concurrent-load results. High availability requires the PostgreSQL/outbox/index architecture described in DESIGN.md. Lexical search currently misses synonym-only queries, heuristic confidence is not calibrated and near-duplicate checks do not scale as a global similarity service.

## Demonstration story

1. Show the two “Kafka consumer lag” documents: same title, different types and IDs.
2. Search one exact ID, then a nonexistent ID. Show that the nonexistent one does not return a similar source.
3. Ask why Kafka lag happened, follow up about impact, then switch to how to handle it.
4. Open the SOP excerpt and compare every step with the stored source.
5. Re-ingest one source unchanged, then edit it. Show stable identity and version increment.
6. Upload a mixed legacy source. Show its review reasons and absence from normal search.
7. Delete a source and show that new searches and old conversation pointers no longer expose it.
8. Run the test suite and evaluator. Show the raw outputs and explain the sample-size limitation.

## Recommended next work

First build an expert-labeled real corpus and integrate enterprise identity. Then measure whether lexical retrieval meets actual query needs. Add semantic retrieval only with measured benefit, and keep procedure delivery extractive. Add source connectors, durable workers, per-source revision checks and production observability once the deployment requirements are known. The explicit cuts and priorities are in CUTS.md.
