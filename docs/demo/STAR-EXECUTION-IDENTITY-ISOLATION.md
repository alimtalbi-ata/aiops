# STAR n8n execution identity

An execution ID is specific to an n8n workflow execution. The stages correlate, enrich, analyze and simulate may use different n8n execution identifiers and must not silently inherit one global execution_id. A future implementation must accept an explicit cue-to-execution-id mapping, fail closed on missing entries, and prohibit inference from run_id or previous stage. Historical Playwright integrity does not attest business state or execution identity. This is an architectural requirement, not a runtime qualification.
