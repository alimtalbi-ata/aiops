alter table aiops.run_events add column if not exists event_key text;
create unique index if not exists ux_run_events_event_key on aiops.run_events(run_id,event_key) where event_key is not null;
