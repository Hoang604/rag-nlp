---
name: stg-ingestion
description: Orchestrates the staging curation lifecycle, enforcing queue draining, graph relational integrity, and zero-violation session commitment under sentinel supervision.
---

# Staging Ingestion & Knowledge Graph Curation Protocol

A transactional protocol for driving a staging session from uncurated text fragments to a validated, referentially closed knowledge graph.

## Context Pointer & Protocol Invariants

When beginning a staging curation task, read `corpus-mcp_interface/instructions.md` in your MCP configuration to load the active semantic invariants

### Strict Operational Boundaries & Prohibitions

- **STRICT PROHIBITION ON READING CODE**: Under NO circumstances should any agent inspect, search, or read application source code, backend services, scripts, or tests anywhere in the repository (`src/`, `scripts/`, `tests/`, etc.).
- **STRICT PROHIBITION ON DIRECT .cache ACCESS**: Under NO circumstances should any agent read, browse, or inspect files directly from `.cache/` or `.cache/stg/`.
- run no command, you are forbid from running any command, no run_command called.
- **EXCLUSIVE TOOL SURFACE**: All discovery, raw source verification, surgical patching, semantic classification, graph relation authoring, integrity validation, and session commitment MUST be conducted EXCLUSIVELY through:
  1. `view_file`: Restricted strictly to operational guidance (`corpus-mcp_interface/instructions.md`), MCP tool schema definitions, or tool outputs when necessary.
  2. Official `corpus-mcp_interface` MCP tools
---

## Curation Execution Steps

### Step 1: Arm Supervision Sentinel (1-Minute Cron)

Initialize a 1-minute recurring background sentinel to maintain vigilance and active context resolution throughout batch processing:

- **Action**: Call `schedule` with:
  - `CronExpression`: `"*/2 * * * *"`
  - `Prompt`: "STAGING SENTINEL: Review every chunk against the Isolation Rule. Classify as REQUIRES_EXTERNAL_CONTEXT whenever meaning depends on the wider document. Assign SELF_CONTAINED strictly when the text stands 100% locally self-sufficient. For every chunk with borrowed meaning (REQUIRES_EXTERNAL_CONTEXT), actively resolve and attach directed relation edges using graph and navigation tools before finalization."
  - `IsDaemon`: `false`
- **Completion Criterion**: The schedule call succeeds and the returned `TaskId` is preserved in memory for terminal teardown.

---

### Step 2: Queue Draining

Select the target document session (`stg_list_sessions`) and continuously curate batches according to protocol invariants until no unreviewed chunks remain.

- **Completion Criterion**: `stg_poll_pending` confirms exactly 0 pending chunks remain in the target session.

---

### Step 3: Pre-Flight Integrity Gate

Verify that the entire session satisfies all relational invariants prior to commitment:

- **Action**: Execute `stg_validate(doc_slug=...)`.
- **Remediation**: If topological or classification violations are reported, use remediation tools (`stg_patch`, `stg_remove_edges`, or `stg_unfinalize_chunks`) until all invariant checks pass cleanly.
- **Completion Criterion**: `stg_validate` reports zero integrity violations.

---

### Step 4: Sentinel Teardown & Session Commitment

Conclude the staging transaction cleanly:

- **Action**:
  1. Terminate the background sentinel task using `manage_task(Action="kill", TaskId=...)`.
  2. Commit the validated session using `stg_commit(doc_slug=...)`.
- **Completion Criterion**:
  - The sentinel cron task is confirmed killed.
  - The staging session transitions to `AGENT_COMMITTED`.
