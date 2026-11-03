# Isolation evidence

The brief mentions “isolation evidence” without defining a tenant boundary. This implementation interprets it as RCA/SOP knowledge isolation and access-role isolation. It does **not** claim tenant or per-service ACL isolation.

| Invariant | Executable evidence |
|---|---|
| Concurrent duplicate sources create one identity | `test_concurrent_renamed_duplicates_from_empty_store` checks 20 source aliases, one document and one version |
| Same-title RCA/SOP are distinct and ambiguous | `test_type_isolation_and_exact_order` creates both, checks both types and ambiguity |
| SOP answers contain only the selected SOP | Same test compares the full returned answer to exact original SOP content |
| Wrong-type selection is rejected | Same test requests an RCA answer with an SOP ID and expects 409 |
| Type-filtered exact ID cannot leak across type | Same test requests an RCA ID under SOP filter and expects zero results |
| Missing explicit identity never gets a lookalike | Same test uses `DOC-MISSING kafka`; expects zero results |
| Follow-ups preserve topic; explicit switch changes it | `test_context_switch` checks RCA -> RCA follow-up -> SOP |
| New incident query does not inherit unrelated old evidence | `test_new_topic_does_not_inherit_wrong_document` checks unrelated/new missing-ID queries abstain |
| Mixed/quarantined sources are hidden from readers | `test_mixed_unknown_near_duplicate_review` checks 404 and curator review queue |
| Deleted content does not remain in search or conversations | `test_version_deletion_no_stale_chat` checks detail, search and old session |
| Reader cannot mutate or inspect review queue | `test_secrets_and_access` expects 403; wrong key expects 401 |
| Submitted secrets are not echoed/stored unredacted | `test_secrets_and_access`, `test_validation_does_not_echo_secret_body` |

Search filters are enforced in database retrieval and chat verifies document kind again. UI columns are an additional visual distinction, not the security boundary. There is no cross-type generated synthesis, prompt-based isolation or shared model memory. Full procedure bodies are delivered exactly after redaction; a redacted procedure is held for review.

Limit: all reader-key holders share the same trust scope, including opaque chat session identifiers. Add per-user identity and ACLs before claiming user/tenant isolation. Operator database access includes historical redacted snapshots even after a document is soft-deleted; application readers cannot access those snapshots.
