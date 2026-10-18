create or replace function aiops.prevent_append_only() returns trigger language plpgsql as $$ begin raise exception 'append-only record'; end; $$;
drop trigger if exists trg_events_immutable on aiops.run_events; create trigger trg_events_immutable before update or delete on aiops.run_events for each row execute function aiops.prevent_append_only();
drop trigger if exists trg_evidence_immutable on aiops.evidence; create trigger trg_evidence_immutable before update or delete on aiops.evidence for each row execute function aiops.prevent_append_only();
