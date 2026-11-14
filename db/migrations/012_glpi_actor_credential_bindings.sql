-- Explicit, revocable OIDC actor -> GLPI user identity bindings.
-- NO API tokens, passwords or secrets stored here. No default/fallback actor.
-- Apply only after a reviewed provisioning process verifies the GLPI user.
create table if not exists aiops.glpi_actor_user_bindings (
    actor_id text not null,
    tenant_id text not null,
    glpi_instance_id text not null,
    glpi_user_id bigint not null,
    verified_at timestamptz not null,
    revoked_at timestamptz,
    primary key (actor_id, tenant_id, glpi_instance_id),
    constraint glpi_actor_user_id_positive check (glpi_user_id > 0),
    constraint glpi_actor_binding_actor_nonempty check (length(btrim(actor_id)) between 1 and 200),
    constraint glpi_actor_binding_tenant_nonempty check (length(btrim(tenant_id)) between 1 and 128),
    constraint glpi_actor_binding_instance_nonempty check (length(btrim(glpi_instance_id)) between 1 and 128)
);
create index if not exists ix_glpi_actor_user_bindings_tenant
    on aiops.glpi_actor_user_bindings(tenant_id, glpi_instance_id)
    where revoked_at is null;
-- Provisioning and revocation are out of scope of the read-only runtime.
-- This table is not an authorization grant by itself: active tenant grant,
-- OIDC/JTI verification, native GLPI ACL and Core/GLPI read ACL still apply.
