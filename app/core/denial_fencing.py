"""V2.8 transactional claim for rejected Critic intents."""

def claim_denials(conn, owner, limit=20, lease_seconds=60):
    if not owner or len(owner) > 128:
        raise ValueError("invalid_claim_owner")
    if not 1 <= limit <= 50:
        raise ValueError("invalid_claim_limit")
    if not 10 <= lease_seconds <= 300:
        raise ValueError("invalid_lease_duration")

    rows = conn.execute("""
        WITH selected AS (
            SELECT o.run_id, o.critique_id
            FROM aiops.critic_denial_outbox o
            JOIN aiops.runs r ON r.run_id=o.run_id
            WHERE o.status='PENDING'
              AND r.status='BLOCKED'
              AND (
                o.lease_expires_at IS NULL
                OR o.lease_expires_at <= now()
              )
            ORDER BY o.created_at, o.run_id, o.critique_id
            FOR UPDATE OF o SKIP LOCKED
            LIMIT %s
        )
        UPDATE aiops.critic_denial_outbox o
        SET lease_owner=%s,
            lease_expires_at=now()+(%s * interval '1 second'),
            fencing_token=o.fencing_token+1,
            attempts=o.attempts+1
        FROM selected s
        WHERE o.run_id=s.run_id
          AND o.critique_id=s.critique_id
        RETURNING o.run_id,o.critique_id,o.analysis_id,
                  o.evidence_ids,o.policy_input,
                  o.lease_owner,o.lease_expires_at,o.fencing_token
    """, (limit, owner, lease_seconds)).fetchall()

    fields = (
        "run_id", "critique_id", "analysis_id", "evidence_ids",
        "policy_input", "lease_owner", "lease_expires_at",
        "fencing_token"
    )
    return [dict(zip(fields, row)) for row in rows]

def validate_finalization(row, owner, token, verdict, now):
    if row["status"] != "PENDING":
        raise ValueError("intent_not_pending")
    if row["lease_owner"] != owner or row["fencing_token"] != token:
        raise ValueError("stale_fencing_token")
    if not row["lease_expires_at"] or row["lease_expires_at"] <= now:
        raise ValueError("lease_expired")
    if row["run_status"] != "BLOCKED" or row["critic_validated"] is not False:
        raise ValueError("critic_denial_not_verified")
    if verdict.get("state") != "BLOCKED" or verdict.get("decision") not in (
        "HUMAN_APPROVAL", "ESCALATE"
    ):
        raise ValueError("unsafe_policy_verdict")
    return True
