# n8n integration pack

n8n is an integration boundary, not the canonical Run Engine. Workflows must call the Portal/Core APIs and never write the AioOps PostgreSQL tables directly.

The workflow below is intentionally importable rather than auto-imported: n8n credentials and ownership are deployment-specific.
