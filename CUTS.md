# Deliberate cuts and next steps

| Cut from running implementation | Reason | Next step |
|---|---|---|
| Hosted LLM generation | Expense, latency and unsafe procedure rewriting; brief prioritizes cost | Evaluate bounded RCA synthesis only if exact excerpts are insufficient; never generate SOP steps |
| Embedding/vector retrieval | Avoid an unmeasured extra service and model dependency | Benchmark local embeddings + lexical hybrid on sealed real-corpus queries |
| Automatic mixed-document splitting | Risk of losing procedure constraints | Add section provenance and curator-confirmed split tooling |
| OCR, DOCX, wiki connectors | Keep file boundary bounded and auditable | Sandboxed extractor workers, DLP and durable connector revisions |
| Enterprise SSO / service ACLs | Not enough organization identity context in brief | Mandatory before use across teams; filter before and after retrieval |
| HA and multi-node writes | Single-node reference minimizes infrastructure | PostgreSQL + transaction outbox + durable indexing workers |
| Sophisticated near-duplicate index | Simple explainable baseline | MinHash candidate index with measured thresholds and merge workflow |
| Sealed production evaluation set | No real corpus or supplied query dataset available | Owner-labeled incident-family split with confidence intervals |
| Streaming suggestion responses | Local calls already return one bounded response | Add SSE only for measured progressive stages |
| Real hosting cost integration | No actual billing environment supplied | Cost tags and monthly attributable spend/request |
| Rich source editor, pagination, user audit UI | Core workflows prioritized | Owner approval, source links, version diff, cursor pagination, per-user audit |
| Automatic source removal reconciliation | No upstream connector configured | Scheduled sync tombstones and optimistic upstream revision checks |
| Full DLP / encryption / network controls | Organization-specific infrastructure | Secret scanner, KMS, TLS ingress, WAF/rate limits, egress policy and backup drills |

No external Git repository was created or published. This folder/ZIP is ready to initialize and push to a private repository under the user's account after normal review. The PDF's submission wording is a deliverable reference, not authorization to access or publish to an account.
