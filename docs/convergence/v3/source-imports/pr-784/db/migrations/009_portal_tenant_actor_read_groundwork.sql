-- Additive tenant/actor read authorization groundwork. NOT a grant of access.
-- Existing Runs remain unbound and therefore invisible to tenant-scoped reads.
-- No backfill, default tenant, inferred actor, or change to legacy endpoints.
create table if not exists aiops.portal_actor_tenant_grants (
    actor_id text not null,
    tenant_id text not null,
    granted_at timestamptz not null default now(),
    revoked_at timestamptz,
    primary key (actor_id, tenant_id),
    constraint portal_actor_id_nonempty check (length(btrim(actor_id)) between 1 and 200),
    constraint portal_tenant_id_nonempty check (length(btrim(tenant_id)) between 1 and 200)
);
create table if not exists aiops.portal_run_tenant_bindings (
    run_id text primary key references aiops.runs(run_id) on delete cascade,
    tenant_id text not null,
    bound_at timestamptz not null default now(),
    constraint portal_run_tenant_nonempty check (length(btrim(tenant_id)) between 1 and 200)
);
create index if not exists ix_portal_run_tenant_bindings_tenant
    on aiops.portal_run_tenant_bindings(tenant_id, run_id);
-- This query is a contract example only, not a deployed endpoint.
-- A trusted server must derive :actor_id; browser-supplied actor/tenant is forbidden.
-- SELECT r.run_id FROM aiops.runs r
-- JOIN aiops.portal_run_tenant_bindings b ON b.run_id = r.run_id
-- JOIN aiops.portal_actor_tenant_grants g ON g.tenant_id = b.tenant_id
-- WHERE g.actor_id = :server_actor_id AND g.revoked_at IS NULL
-- ORDER BY r.created_at DESC, r.run_id DESC LIMIT 100;
