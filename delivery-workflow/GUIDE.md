# Delivery Workflow: deliver software with evidence you can resume

> Documentation of the existing project at `ddac35ef8362d1f93356142ca7f651888f2146e5`, not a new runner or a completed delivery. Source references are monorepo-relative.

## Quickstart

- **Purpose:** carry an idea or substantial existing-system change through implementation, actual verification and documented handover.
- **Why not ordinary coding chat?** The reusable contract makes scope, phase choices, recorded evidence and resumption explicit. A small Python coordinator returns the next assignment and checks saved records. It does not make the model smarter, write the product by itself or deploy it. Small known edits and read-only questions usually need no full workflow.
- **Good fit:** connected changes, uncertain implementation paths and work resumed across sessions. An empty project folder is a valid start.
- **Prepare:** a host that can read instructions, edit the authorized project, execute local commands, preserve real evidence and resume; Python 3.10+, PyYAML, jsonschema and Git; approved private records/configuration locations outside all Git ancestors and the package.
- **First action:** supply `delivery-workflow/SKILL.md` and its references through the host's documented mechanism. Use the request below; no universal slash command is assumed.
- **Expected result:** working files and usage instructions, real verification evidence, retained receipts and a report. A successful final `check` establishes evidence completion—not publication or semantic correctness.

```text
Outcome → private task → audit → host designs/builds/checks
                            ↑                ↓
                       next assignment ← record real evidence
                                             ↓
                               postmortem → check → handover
```

**Suggested user prompt, composed from the existing contract:**

> Use Delivery Workflow to implement this scoped change in <project-folder>: <outcome>. Reuse the existing design and tests. Agree only unresolved material choices and permission boundaries. Keep private task/evidence records outside Git, verify the actual changed artifact, and hand over working files, use instructions, actual checks and remaining gaps. Do not commit, push, deploy or schedule without separate authorization.

This is an ordinary-language request, not a new CLI. The primary introduction remains `delivery-workflow/START-HERE.html`; `delivery-workflow/README.md` remains the canonical command quickstart. `delivery-workflow/demo.html` shows a hypothetical document tool, not an execution record.

## Prepare once without weakening the storage guard

Keep the package intact. Check that the host can read referenced instructions and evidence, execute commands and resume saved work. A chat-only host cannot perform this workflow. No model API, fixed model, automatic reviewer fleet or inference engine is included. Remote issue/PR sources and independent review require separate authorized capabilities.

Use one interpreter throughout. If dependencies are missing, obtain approval for an isolated environment using `delivery-workflow/requirements.txt`; do not change global packages implicitly. Project code stays in its workspace. Tasks, receipts, reports, optional board and learning stay in approved private storage. Configuration also must be outside every Git ancestor and the installed package. An ignored folder remains ineligible.

`DELIVERY_WORKFLOW_HOME` explicitly selects the private root; `DELIVERY_WORKFLOW_ROOT` is its alias. Otherwise the remembered pointer is at `$XDG_CONFIG_HOME/delivery-workflow/config.json`, defaulting to `~/.config/delivery-workflow/config.json`. These are public configuration conventions, not personal account values. Ask before substituting an unavailable root.

Sources: `delivery-workflow/README.md:14–29`; `delivery-workflow/references/execution.md:7–25`.

## Existing CLI: action, result and next step

From the monorepo root, after choosing approved locations and preparing a real private task using `delivery-workflow/references/task-template.md`:

```text
<python> -c "import yaml, jsonschema"
<python> delivery-workflow/scripts/arc_run.py configure --root <approved-private-folder>
<python> delivery-workflow/scripts/arc_run.py audit <private-task.md> --project <workspace>
<python> delivery-workflow/scripts/arc_run.py record <returned-run-dir> --receipt <actual-receipt.json>
<python> delivery-workflow/scripts/arc_run.py status <returned-run-dir>
<python> delivery-workflow/scripts/arc_run.py check <returned-run-dir>
```

Replace placeholders; these are not commands to run sequentially without intervening work. `configure` writes private configuration. `audit` inspects the workspace and validates the proposed phase decisions, returning a run location and next assignment. The host then **performs that work and saves evidence** before `record`. Record each included phase immediately and in catalog order. `status` provides the next assignment after interruption. Only final `check` with `status: complete` establishes evidence completion.

Exit 0 means the step was processed; read the status rather than treating it as delivery success. Exit 1 means blocked/failed/stopped; exit 2 means flagged. `check --dry-run` is **not read-only**: it writes check results, reports and possibly ledger events. None of these commands was executed as a product run for this guide.

Sources: `delivery-workflow/references/execution.md:27–44,97–103`; `delivery-workflow/scripts/arc_run.py:148–256,289–348`.

## How scope becomes evidence

The host reads existing design, instructions, inputs and implementation before writing the private task. It selects necessary phases, giving allowed reasons and actual evidence for exclusions. `understand`, `verify` and `postmortem` remain mandatory. Existing adequate build coverage can justify the defined `EXISTING_BUILD_COVERAGE` exclusion for constraints/tdd; do not manufacture a red test merely to populate a phase.

The coordinator calls real local helper scripts for preflight and validation; these calls are distinct from host-led coding, research, testing or deployment. Receipts refer to actual evidence files, not assertions that work must have happened. During record, the coordinator checks run identity, ordering, prior receipt digests and manifest-bound requirements. It validates the submitted receipt, saves it, validates that saved copy and adds its digest to the ledger. Final check revalidates the record chain.

`verify` requires at least one passing `kind: live` check. Here “live” means a direct check of the actual changed artifact or behavior, not necessarily production or network activity. A synthetic fixture is not proof of recipient-host behavior. If independent review is required, an actual separate reviewer must examine the candidate; structural validation or self-review cannot substitute for that gate.

Sources: `delivery-workflow/SKILL.md:21–76,96–102`; `delivery-workflow/references/execution.md:46–103`; `delivery-workflow/scripts/arc_run.py:208–256`.

## Expected artifacts and completion boundary

In the private run under `arc_runs`, expect `run.json`, `preflight_result.json`, `manifest.yaml`, `lessons_snapshot.yaml`, `audit_result.json`, `receipts/<phase>.json`, `ledger.jsonl`, reports and eventually `check_result.json`. The project workspace contains the actual product, design and use instructions. Optional private learning and a SQLite board are not required for a small workflow.

A handover should identify the product path and actual use/preview command, checks performed, open gaps and saved report. Report **working changes, commits and publication separately**. The coordinator does not commit, push, deploy, schedule or send messages. Structural checks cannot prove that cited commands actually ran or that implementation semantics are correct.

Sources: `delivery-workflow/scripts/arc_run.py:105–190,289–326`; `delivery-workflow/SKILL.md:78–102`.

## Human boundaries and safe recovery

- Build permission does not authorize destructive live actions, external communication, deployment, scheduling or Git mutations. Preserve unrelated work. Ask only at material choices and permission boundaries, not at every routine phase.
- For interruption, run `status <run>` and reread the saved task, relevant evidence and current workspace. Do not infer completed work from a remembered chat summary.
- Changed task/scope needs a newly audited run. Preserve the previous report; never hand-edit approval, hashes or ledger events to make a run pass.
- A flagged dirty-worktree preflight may use `--force --override-reason` only for authorized handling of existing changes. That override cannot waive manifest/audit failure.
- An `INVALIDATED` spike stops downstream work. Reassess the approach and start a revised audited run; do not record later phases as though the experiment passed.
- Inspect interrupted writes and locks before recovery. Existing receipt destinations are not permission to overwrite evidence. Standalone manifest generation refuses existing destinations/symlinks: choose a new authorized filename.
- Missing sources, required review or host capabilities remain explicit blockers. Do not invent evidence, weaken private-path guards or substitute a UI for unsupported execution.

Sources: `delivery-workflow/SKILL.md:43–54,78–102`; `delivery-workflow/README.md:31–37`; `delivery-workflow/references/execution.md:35–44,190–192`.

## Technical depth and evidence limits

Open adjacent `walkthrough.html`. It embeds every runtime Python class/function, whole modules including imports and CLI dispatch, and all contract/config/schema authorities. The map distinguishes implemented helper subprocess calls from artifact handoffs, harness work and human permission. The receipt-binding slice explains where records are checked and what they cannot prove.

The walkthrough is source-only: no target workflow, production call or model call was executed. This export contains no Delivery tests, and no successful recipient-host end-to-end run is claimed. Optional governance requirements are selected by the task contract; the governance-size ceiling is a host measurement obligation, not automatically discovered by `check`.
