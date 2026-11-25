---
name: delivery-workflow
author: Roland Chotika
license: MIT
description: Build a tool or system from an idea through design, implementation, integration and verification, or carry a substantial existing-system change through that cycle. Use for an explicit Delivery Workflow request or a build with uncertain, dependent parts; small known edits and read-only questions usually need no full workflow.
metadata:
  version: "0.3.0-neutral-export"
---

# Delivery Workflow

Deliver working software and its use instructions, supported by saved evidence.
An idea and empty project folder are valid starting points. The host agent does the
work; the existing Python runner coordinates and validates records. No model client,
fixed model, independent deliberation installation or extra agent fleet is required.

Use this entry point during execution. [DESIGN.md](DESIGN.md) is the maintenance
source of truth; consult a specific section for a real contract question, not the whole history.
Load only the relevant [execution reference](references/execution.md) section below.

## Begin

1. Resolve/create the requested project folder. Read its instructions, canonical
   design, relevant inputs and existing implementation. Reuse valid preparation.
   If the outcome or decision to build is unresolved, clarify first; optional
   requirements discovery can help. A scoped implementation request needs no repeated approvals.
   Ask only about material choices or actual permission boundaries. Implementing a
   destructive tool does not authorize live deletion.
2. On first use, ask for a personal folder outside Git and this skill; never guess
   a replacement for an unavailable configured root. Read **Install and prepare**
   in the execution reference; use one Python 3.10+ interpreter with PyYAML and
   jsonschema. `configure --root` remembers the location. Project code stays in the
   workspace; tasks, evidence, reports, optional board and lessons stay private.
3. Read relevant [seed guidance](kb/delivery_workflow_kb.md) and personal method lessons;
   they are advice, not facts or automatic gates. For issue/PR sources or confirmed
   learning, use the needed section of [sources and learning](references/sources-and-learning.md).
4. Write the private task from [task-template.md](references/task-template.md),
   identifying outcome, project, sources, scope, deliverables and checks. Select
   necessary phases internally; exclusions need allowed reasons and real evidence.
   Reuse `EXISTING_BUILD_COVERAGE` for constraints/tdd when sufficient; do not invent
   tests merely to fill phases. Run `audit <task> --project <workspace>`.

Resolve flagged/blocked audits and audit the revised task. Never hand-edit approval.
Use a preflight override only for authorized handling of existing unrelated edits;
`--force --override-reason` cannot waive an audit failure.

## Work on the next phase

Use `scripts/arc_run.py` with the selected interpreter. Audit/record return the next
phase and short assignment. Execute included phases in catalog order and call
`record <run> --receipt <file>` immediately after each, before the next. Read
**Receipts** in the execution reference when preparing evidence; use its current
phase row and absolute file references. Required phases remain understand, verify
and postmortem. An INVALIDATED spike stops downstream work.

Build the requested behavior even when process phases are excluded. Connect affected
components and check the actual artifact. When replacing a path, trace callers,
configuration and failure routes; retire the old implementation and entry points.
Read **Retiring replaced code paths** when relevant. Verify both the replacement
and absence of re-entry into invalid behavior. Keep inaccessible consumers visible.

An available native subagent may handle one substantial bounded research or
verification task. Pass the goal, necessary sources/decisions, allowed tools and
expected evidence; prohibit further delegation. The main agent integrates results
and writes runner state serially. Small tasks or unavailable delegation stay direct;
never delegate each phase automatically or invent an agent result.

## Keep checks proportionate

Enforce **total governance LOC <= product LOC** for the maintained target project.
Before adding controls or removing product code, use the execution reference's
**Measuring the governance ceiling** and its linked counting contract. Remove obsolete
controls and callers; never pad product code or waive the limit. Reuse existing
checks and stop expanding them once criteria pass. Tests/fixtures/development tools
stay out of shipped product modules, dependencies and startup. Necessary product
validation remains. Optional governance evidence is loaded only when selected.

## Resume and finish

After interruption, `status <run>` returns the next assignment. Read the saved task,
needed evidence and current project state. Changed task/scope requires a new audited
run; preserve old reports. Inspect locks/interrupted writes rather than deleting
or fabricating records. Reassess repeated failure without new evidence.

Maintain the project design and usage instructions. Record the actual outcome,
gaps, retired paths/controls, cleanup and retained evidence in postmortem. Snapshot
required evidence before intentional deletion. Learning is optional.

Run `check <run>`; only `status: complete` establishes evidence completion. Deliver
product path, exact use/preview command, actual checks, open gaps and saved report.
Report working changes, commit and publication separately; the runner does not
publish, schedule or send anything. Keep unperformed host/live checks open.
Save only user-supplied or confirmed method learning using **Personal learning and
optional board**; no mandatory reflection, case knowledge in the KB or review of reviews.

## Harness and authority boundaries

The harness must read the full contract and referenced evidence, execute authorized local tools, preserve actual outputs and resume the saved task. A chat-only host cannot perform this workflow. No particular agent API, install path, model or discovery command is required or promised compatible.

When the project or user requires independent review, use a genuinely separate reviewer with read-only access to the exact candidate and relevant evidence. Self-review or the structural `check` result is not independent approval. If independent review is unavailable, leave that gate open; do not manufacture a reviewer result. Keep reviewer observations separate from the implementer's response. No extra review is mandatory merely because this workflow is used.

Human permission boundaries remain binding for destructive operations, external communication, scheduling, deployment and Git mutations. Existing unrelated work must be preserved. The coordinator's Git inspection does not authorize a commit, push or publication, and evidence completion does not prove any of them happened.
