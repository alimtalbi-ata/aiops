# ACME AioOps 2.0 — Architecture

## Design principle
The platform is rebuilt as a clean runtime. Legacy version names are not part of the new domain model. The existing Docker images are treated as reusable technology inputs; runtime containers, databases, identifiers, networks and APIs are normalized.

## Authorities
- **Core**: canonical Run lifecycle, idempotency, optimistic versioning, append-only event journal.
- **Twin**: authoritative topology and synthetic-state model; services/applications/business layers are first-class nodes.
- **Evidence**: immutable evidence records with payload hash and provenance.
- **Policy**: fail-closed decision gate; LIVE actions cannot silently become autonomous.
- **Worker + Temporal**: sole execution engine for a Run.
- **Portal**: read/command experience; never writes databases directly.
- **Simulator**: synthetic scenario generator; never receives data-network access.
- **n8n**: external integration boundary; it calls Core APIs and does not own state.

## Networks
`aiops-public` only reaches the Portal. `aiops-control` carries application control calls. `aiops-data` contains databases and data services. `aiops-execution` is isolated for Worker/Simulator execution. `aiops-temporal-data` is dedicated to Temporal's database. `aiops-integration` isolates GLPI/n8n.

## Run stages
INGEST → NORMALIZE → CORRELATE → CMDB → OBSERVE → RAG → DGX_ANALYST → DGX_CRITIC → POLICY → HITL → REMEDIATE → VERIFY → RECONCILE → LEARN.

Each stage has a durable state, evidence references and an event. A Run is versioned; commands require the expected version. Duplicate commands are returned from `command_receipts`.

## Twin model
The Twin contains business services, applications, compute, storage, SAN, network and NAS. Edges carry relation type, redundancy and confidence. `twin_facts` stores valid-time plus known-time facts so the system can answer what was known at a historical moment.

## Safety
DEMO/REPLAY/STORY can mutate only explicitly synthetic Twin state. LIVE resolution/remediation requires a policy/HITL path. Evidence records and Run events are append-only at database level.
