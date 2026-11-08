# AIOps2 — instructions for Codex and coding agents
Read `docs/architecture/AIOPS2-MULTIAGENT-ORCHESTRATION.md`, `docs/PROJECT-CONTINUITY.md`, `docs/COMPONENT-CATALOG-AND-REUSE.md`, `docs/architecture/AIOPS2-GITHUB-REUSE-INVENTORY-2026-11-08.md`, and the role's GitHub issue before coding.

Search existing implementations across branches/PRs/history before creating new code; absence on one branch is not absence in the project. Protect Debian runtime and Policy/Critic/HITL. One issue, one branch/worktree, one DRAFT PR; don't modify shared canonical docs except via Integration. Record exact SHA, tests actually run, CI links, source-vs-Debian distinction, risks and rollback in role-specific handoff. Do not invent E2E PASS or deploy evidence.

Never merge, auto-deploy, run remote commands, mutate GLPI/PostgreSQL, create duplicate tickets, change cron/Compose, bypass Policy/HITL or modify production without explicit separate approval. The five scheduled ChatGPT roles do not automatically create Codex execution sessions.
