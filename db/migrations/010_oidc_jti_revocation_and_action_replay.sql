-- Durable OIDC JTI revocation and one-time sensitive-action replay barriers.
-- No token contents or signing material are stored. Rows must be retained at least
-- through token/action expiry plus clock skew; do not prune valid rows.
create table if not exists aiops.oidc_jti_revocations (
    issuer text not null,
    jti text not null,
    expires_at timestamptz not null,
    revoked_at timestamptz not null default now(),
    reason text not null default 'operator_revocation',
    primary key (issuer, jti),
    constraint oidc_revocation_issuer_nonempty check (length(btrim(issuer)) between 1 and 512),
    constraint oidc_revocation_jti_nonempty check (length(btrim(jti)) between 1 and 512),
    constraint oidc_revocation_reason_nonempty check (length(btrim(reason)) between 1 and 200)
);
create index if not exists ix_oidc_jti_revocations_expiry
    on aiops.oidc_jti_revocations(expires_at);

create table if not exists aiops.oidc_sensitive_action_consumptions (
    issuer text not null,
    jti text not null,
    action_id text not null,
    consumed_at timestamptz not null default now(),
    expires_at timestamptz not null,
    primary key (issuer, jti, action_id),
    constraint oidc_action_issuer_nonempty check (length(btrim(issuer)) between 1 and 512),
    constraint oidc_action_jti_nonempty check (length(btrim(jti)) between 1 and 512),
    constraint oidc_action_id_nonempty check (length(btrim(action_id)) between 1 and 200)
);
create index if not exists ix_oidc_action_consumptions_expiry
    on aiops.oidc_sensitive_action_consumptions(expires_at);
