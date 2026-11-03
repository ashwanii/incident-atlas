# Kafka consumer lag
## Prerequisites
On-call approval and read access to consumer metrics.
## Steps
1. Record consumer group offset and current lag.
2. Confirm processing errors and partition assignment.
3. Obtain incident commander approval before scaling consumers.
4. Scale only within the approved capacity limit.
## Verification
Confirm lag decreases for ten consecutive minutes.
## Rollback
Restore the previous consumer replica count if errors increase.
