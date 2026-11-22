-- #203: append-only Core xref and independently scoped resource ownership.
-- No GLPI write path. A separate trusted integration adapter is required to ingest.
create table if not exists aiops.tenant_resource_ownership (
 resource_kind text not null check(resource_kind in ('incident','run','glpi_instance','glpi_ticket','glpi_entity')),
 resource_id text not null, tenant_id text not null, source_event_id text not null,
 verified boolean not null default false, observed_at timestamptz not null,
 known_at timestamptz not null default now(), primary key(resource_kind,resource_id),
 check(observed_at<=known_at)
);
create table if not exists aiops.itsm_xref_events (
 association_id text primary key, tenant_id text not null, glpi_instance_id text not null,
 ticket_id text not null, glpi_entity_id text not null,
 incident_id text not null references aiops.incidents(incident_id),
 run_id text not null references aiops.runs(run_id),
 source_event_id text not null unique, mapping_version integer not null check(mapping_version>=1),
 event_type text not null check(event_type in ('VERIFIED','REVOKED')),
 actor_id text not null, observed_at timestamptz not null, known_at timestamptz not null,
 supersedes_association_id text references aiops.itsm_xref_events(association_id),
 verification_method text not null check(verification_method='AUTHENTICATED_ID_READBACK'),
 provenance text not null check(provenance='AUTHENTICATED_SOURCE_API'),
 glpi_ticket_readback_verified boolean not null, core_run_readback_verified boolean not null,
 source_payload_hash text not null check(length(source_payload_hash)=64),
 attestation_mac text not null check(length(attestation_mac)=64),
 unique(tenant_id,glpi_instance_id,ticket_id,mapping_version),
 check(observed_at<=known_at)
);
create index if not exists ix_itsm_xref_lookup on aiops.itsm_xref_events
 (tenant_id,glpi_instance_id,ticket_id,mapping_version desc);
create or replace function aiops.prevent_itsm_xref_mutation()
returns trigger language plpgsql as $$
begin raise exception 'immutable Core xref provenance'; end;
$$;
drop trigger if exists trg_itsm_xref_immutable on aiops.itsm_xref_events;
create trigger trg_itsm_xref_immutable before update or delete on aiops.itsm_xref_events
 for each row execute function aiops.prevent_itsm_xref_mutation();
drop trigger if exists trg_itsm_owner_immutable on aiops.tenant_resource_ownership;
create trigger trg_itsm_owner_immutable before update or delete on aiops.tenant_resource_ownership
 for each row execute function aiops.prevent_itsm_xref_mutation();
