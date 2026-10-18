# Security and secrets

The development kit defaults to `Newaiops26$` because this environment is explicitly a development/demo environment. Before production, replace every default secret and use Docker secrets or an external secret manager.

The password must not be printed by diagnostics, committed into source control outside the demo `.env` template, or copied into logs. The n8n sample workflow contains the demo token only to make a first deployment immediately demonstrable; production imports should replace it with an n8n credential.
