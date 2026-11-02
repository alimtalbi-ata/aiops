-- Core-only proposal: durable fail-closed OIDC delegation replay/revocation fence.
-- Apply strictly AFTER installed 009 AI, 010 Evidence, 011 HITL, 012 xref.
-- No GLPI write, human ALLOW, execution or live effect is introduced.
create table if not exists aiops.actor_delegation_nonce_ledger (
 schema_version text not null default 'aiops.core-actor-delegation-replay.v1'
   check (schema_version = 'aiops.core-actor-delegation-replay.v1'),
 tenant_id text not null check (length(tenant_id) between 2 and 96),
 issuer text not null check (length(issuer) between 1 and 256),
 subject_sha256 char(64) not null check (subject_sha256 ~ '^[0-9a-f]{64}$'),
 jti_sha256 char(64) not null check (jti_sha256 ~ '^[0-9a-f]{64}$'),
 nonce_sha256 char(64) not null check (nonce_sha256 ~ '^[0-9a-f]{64}$'),
 resource_sha256 char(64) not null check (resource_sha256 ~ '^[0-9a-f]{64}$'),
 expires_at timestamptz not null,
 consumed_at timestamptz not null default clock_timestamp(),
 primary key (issuer, jti_sha256),
 unique (tenant_id, nonce_sha256),
 check (expires_at > consumed_at)
);
create table if not exists aiops.actor_delegation_revocations (
 issuer text not null check (length(issuer) between 1 and 256),
 jti_sha256 char(64) not null check (jti_sha256 ~ '^[0-9a-f]{64}$'),
 source_event_id text not null check (length(source_event_id) between 2 and 128),
 revoked_at timestamptz not null default clock_timestamp(),
 primary key (issuer, jti_sha256)
);
-- Immutable audit facts: no UPDATE/DELETE, even for a repeated migration.
drop trigger if exists trg_actor_nonce_immutable on aiops.actor_delegation_nonce_ledger;
create trigger trg_actor_nonce_immutable before update or delete
 on aiops.actor_delegation_nonce_ledger for each row
 execute function aiops.prevent_itsm_xref_mutation();
drop trigger if exists trg_actor_revocation_immutable on aiops.actor_delegation_revocations;
create trigger trg_actor_revocation_immutable before update or delete
 on aiops.actor_delegation_revocations for each row
 execute function aiops.prevent_itsm_xref_mutation();

-- Both operations serialize on the same issuer/JTI lock, preventing a
-- concurrent revocation from racing a consume within committed transactions.
-- Callers MUST authenticate issuer/tenant/actor before invoking these functions.
create or replace function aiops.actor_delegation_consume(
 p_tenant text, p_issuer text, p_subject_hash text, p_jti_hash text,
 p_nonce_hash text, p_resource_hash text, p_expiry timestamptz)
returns boolean language plpgsql security invoker as $$
declare v_now timestamptz := clock_timestamp(); v_rows integer;
begin
 if p_tenant is null or length(p_tenant) not between 2 and 96
    or p_issuer is null or length(p_issuer) not between 1 and 256
    or p_subject_hash !~ '^[0-9a-f]{64}$'
    or p_jti_hash !~ '^[0-9a-f]{64}$'
    or p_nonce_hash !~ '^[0-9a-f]{64}$'
    or p_resource_hash !~ '^[0-9a-f]{64}$'
    or p_expiry is null or p_expiry <= v_now
    or p_expiry > v_now + interval '5 minutes' then
  return false;
 end if;
 perform pg_advisory_xact_lock(hashtextextended(p_issuer || ':' || p_jti_hash, 0));
 if exists(select 1 from aiops.actor_delegation_revocations
           where issuer=p_issuer and jti_sha256=p_jti_hash) then
  return false;
 end if;
 insert into aiops.actor_delegation_nonce_ledger
 (tenant_id,issuer,subject_sha256,jti_sha256,nonce_sha256,resource_sha256,expires_at)
 values (p_tenant,p_issuer,p_subject_hash,p_jti_hash,p_nonce_hash,p_resource_hash,p_expiry)
 on conflict do nothing;
 get diagnostics v_rows = row_count;
 return v_rows = 1;
end;
$$;
create or replace function aiops.actor_delegation_revoke(
 p_issuer text, p_jti_hash text, p_source_event_id text)
returns boolean language plpgsql security invoker as $$
declare v_rows integer;
begin
 if p_issuer is null or length(p_issuer) not between 1 and 256
    or p_jti_hash !~ '^[0-9a-f]{64}$'
    or p_source_event_id is null or length(p_source_event_id) not between 2 and 128 then
  return false;
 end if;
 perform pg_advisory_xact_lock(hashtextextended(p_issuer || ':' || p_jti_hash, 0));
 insert into aiops.actor_delegation_revocations(issuer,jti_sha256,source_event_id)
 values (p_issuer,p_jti_hash,p_source_event_id) on conflict do nothing;
 get diagnostics v_rows = row_count;
 return v_rows = 1;
end;
$$;
