# Execution reference

Use `SKILL.md` for the normal method. Read only the section needed for the current action here;
`DESIGN.md` holds maintenance rationale and the linked counting contract. The agent issues
commands and writes payloads; the user supplies the task and material missing context.

## Install and prepare

Keep this folder intact. Load `SKILL.md` through the host harness's documented local-instruction or skill mechanism. No installation path, slash command or discovery mechanism is assumed. If discovery is unavailable, explicitly supply the file and its references to a capable harness. Confirm that it can read referenced files, edit the authorized project, execute commands, retain actual outputs and resume saved state. This package supplies no inference engine or connector.

Use one Python 3.10+ interpreter with PyYAML and jsonschema for every command. Check with `<python> -c "import yaml, jsonschema"`. If installation is needed, use a user-approved isolated virtual environment and `requirements.txt`; avoid global changes. Git must be installed, including for reliable no-Git workspace detection. Local folder access and subprocess execution are required. The HTML pages work offline.

Both the personal root and configuration path must be outside **every Git ancestor** and outside the installed skill. Ignored folders inside a repository are still rejected. `DELIVERY_WORKFLOW_HOME` explicitly selects the personal root; `DELIVERY_WORKFLOW_ROOT` is its alias. Otherwise configure stores the pointer under `$XDG_CONFIG_HOME/delivery-workflow/config.json`, defaulting to `~/.config/delivery-workflow/config.json`. Choose authorized paths on the execution host; do not guess a substitute when an existing root is unavailable. There is no automatic migration of another installation's state.

This is a runtime-folder export, not a development checkout. Tests, fixtures, build tooling and archives are excluded. The existing development tests were inspected and attempted separately; no successful full recipient-host run is implied by shipping this folder.

For a new tool, first create the requested project directory, inspect the sample inputs and record
the intended behavior and design. It may be empty and need not have Git history. The `understand`
receipt's legacy `code_ref` field can point to the inspected input, specification or environment
evidence when no implementation exists yet; never invent an existing code path.

The runner invokes `preflight_worktree.py` with its own interpreter; no Bash is required for normal
operation. Git must be available for reliable project inspection, even for declaring a non-Git
workspace. Host access to the selected local folders is required. A remote workspace needs a
personal path accessible on that same host; a laptop path is not automatically available remotely.

```text
<python> <skill>/scripts/arc_run.py configure --root <personal-folder>
<python> <skill>/scripts/arc_run.py audit <personal-task.md> --project <workspace>
<python> <skill>/scripts/arc_run.py record <returned-run-dir> --receipt <receipt.json>
<python> <skill>/scripts/arc_run.py status <returned-run-dir>
<python> <skill>/scripts/arc_run.py check <returned-run-dir>
```

Runner exit codes: 0 for a successfully processed step (read its status), 1 blocked/failed/stopped,
2 flagged. `approved` after audit is permission to begin the phases, not completion. `incomplete`
after record means more work remains. `complete` comes only from the final check. Standalone
manifest validation uses 0 approved, 1 blocked, 2 flagged. `--dry-run` is retained on `check` for
compatibility; both forms WRITE private check results, reports and possibly ledger events. Neither form pushes. This is not a write-free dry run.

For existing unrelated edits, inspect their scope. An authorized preflight override uses
`--force --override-reason "<specific handling of existing changes>"`. It never accepts a failed
manifest. Revise the private task and run audit again to resolve flagged phase/governance decisions;
retain the earlier run. Never hand-edit `audit_result.json`, hashes or the ledger to make it pass.

## Receipts

Save each phase's observed evidence before recording it. Use absolute evidence paths, including
any private copy of command output. Every receipt has this envelope:

```json
{
  "run_id": "<exact run ID returned by audit>",
  "phase": "understand",
  "gate": "Inspected the existing data path and project state",
  "ok": true,
  "timestamp": "<actual ISO-8601 UTC timestamp>",
  "evidence": {
    "preflight": {"status": "clean", "evidence_ref": "<run>/preflight_result.json"},
    "problem_ref": "<private-task.md>",
    "code_ref": "<inspected source file and line>"
  }
}
```

For a preflight override use `status: override`; retain its reason in the task/evidence.
Other phase `evidence` payloads:

| Phase | Required fields |
| --- | --- |
| spike | `verdict: VALIDATED\|PARTIAL\|INVALIDATED`, `evidence_ref` |
| plan | `plan_ref`; optional `kanban: {board_db, task_ids}` |
| constraints | `validator_ref`, observed `good_case_exit_code: 0`, `bad_case_exit_code: 1` |
| tdd | `red_ref`, `green_ref`, observed `suite_exit_code: 0` |
| integration | `activation_ref`, `fallback_ref` |
| cron | `cron_schedule`, `artefact_path`, `artefact_valid: true` |
| doc | `updated_docs: [<actual files>]` |
| verify | `checks: [{name, kind, status, evidence_ref}]`; at least one `kind: live`, all `status: pass` |
| postmortem | `postmortem_ref`, `lessons: {extracted: [], guard_impulse: []}`, `cleanup: {proof_artifacts: [<retained files>], process_artifacts_removed: [], gitready: true}` |

`live` means a direct check of an actual changed artifact or behavior, not necessarily production
or a network call. A synthetic unit fixture is not a live host test. Use `gitready: true` only when
the scoped files and cleanup have been reviewed; it does not assert a commit or push. If a fallback
is inapplicable, cite a real explanation with the integration contract rather than fabricate a run.
Never change an observed exit code to the expected one. A failing check cannot be recorded as done.

For `constraints` and `tdd`, use `EXISTING_BUILD_COVERAGE` when existing build checks already cover
the required behavior. Cite the coverage and run those checks during verification. Do not invent
failing runs or add another validator solely to fill a phase. A constraints validator may be an
existing pipeline check; it need not become a separate runtime component.

Execute automated tests and direct artifact checks in the build/acceptance pipeline. Inspect the
shipping artifact and its ordinary entry point for test modules, fixtures, test dependencies and
startup test hooks. Required product input validation and authorization are ordinary application
behavior; they are not a reason to ship test runners or self-tests.

Successful `audit` and `record` return a short `assignment` for the next included phase, drawn
from the existing catalog. `status` returns that assignment on resumption; it reports a stopped
run or invalid audit instead of suggesting more phase work. No new state format is introduced.

`record` validates the actual run ID, next phase, evidence paths and manifest-bound requirements.
It copies the valid receipt, records its digest and updates the report. Retain the source logs and
postmortem. If a run stops, link its incomplete/stopped report with the remaining problem.

## Measuring the governance ceiling

Follow the [counting contract](../DESIGN.md#governance-size-ceiling). Use an available source counter
or a small one-off build measurement, with the same comment/blank handling on both sides. Retain
the command or measurement code, revision, counted paths/sections and P/G totals in existing task
and verification evidence. Count project-specific measurement code itself under G; do not add a
new counter framework, manifest field or approval cycle. A rename or move must not change ownership.

Measure the baseline before changes, check the projected budget before adding control code or
removing product code, and recount the result. Add the result to the existing verify `checks` list:
`name: governance-size`, `kind: build`, `status: pass` only when **G <= P**, and `evidence_ref` to
the actual measurement. Use `status: fail` for an excess; the existing validator rejects it.
An unknown count is unresolved, not zero. This check does not replace the required direct artifact
check. The runner validates the receipt status and evidence path; classification and counting remain
the agent's responsibility. Do not claim the runner automatically discovers excess governance.

## Retiring replaced code paths

Treat replacing an internal path as integration work even without an external service or new API.
`NO_INTEGRATION_POINT` cannot justify skipping that work. Before editing, trace the affected callers
and entry points: imports/calls, registries and callbacks, configuration/flags, scheduled jobs,
fallback branches and generated copies as applicable. Use searches plus inspection of actual dispatch.
Switch each consumer or remove it; delete the obsolete implementation and hooks. If deletion is
temporarily blocked, disable all access to the invalid behavior and explain the remaining cleanup.
Do not keep a flag, alias or error fallback that can silently select it again.

In the build pipeline, exercise the replacement from the affected entry points and check that
errors or relevant alternate configurations cannot re-enter the retired implementation. Check the
actual built artifact as well as the source. An empty search result or a passing new-function test
alone does not establish this. Reuse relevant coverage; add only missing checks for this failure.

Use the existing `activation_ref` for caller disposition and observed routing checks, and
`fallback_ref` for failure handling without re-entry. Both may cite the same evidence file; if a
consumer map is already selected, extend that file instead of creating another inventory. Include
these results in the existing verify checks and record removals or unresolved consumers in closeout.
No extra receipt field or governance module is needed. A consumer that could not be inspected or
exercised remains an explicit verification gap, not evidence of completed retirement.

## Conditional governance evidence

Use `governance_ack` objects in task frontmatter. Each names `module`, `status` and a reason or
planned evidence. `not_applicable` requires a concrete reason. Task-body triggers are hints to assess
relevance and only add advisory notes; a word match does not require a new acknowledgment or guard.
Only explicitly included modules impose their additional receipt requirements. A lesson marked
`not_applicable` with a reason is resolved without blocking the run.

- `consumer_map`, when included: the verify receipt contains
  `governance.consumer_map.consumer_map_ref`. The referenced file has `## Grep Evidence`, actual
  search results, and a `Hardcoding` column showing how consumers were checked.
- `quality_regression`, when included: use `anchor_ref` and `regression_review_ref` under
  `governance.quality_regression`. If no anchor exists, set `status: anchor_missing` and provide
  `missing_anchor_for` and `proposed_anchor_path`. That limitation remains a warning.
- `pipeline_chunking`, when included: acknowledge `input_validator_ref`, `validator_command` and
  `validator_output_ref` at planning time. The verify evidence repeats the two file references and
  `llm_run_started_at`. The saved validator JSON contains `verdict: pass` and an earlier `timestamp`.
  Use actual timezone-aware timestamps, never a guessed ordering.

The runner always binds verify validation to its own manifest. Supplying another `manifest_ref`
inside a receipt cannot bypass required governance.

## Personal learning and optional board

After the real user's optional method reflection, write a private JSON entry with `id` (`P-...`),
`purpose: skill_improvement`, `rule`, `context`, `limits`, and a narrow `trigger` (`keyword` regex,
`phase_included`, or `deliverable_glob`). Then run:

```text
<python> <skill>/scripts/lessons.py learn --run <run> --entry <entry.json> --reply <actual-user-reply>
<python> <skill>/scripts/lessons.py list
<python> <skill>/scripts/lessons.py retire <id> --reason "The old workflow no longer exists"
<python> <skill>/scripts/lessons.py remove <id> --reason "Replaced by the current build check"
```

No case results belong in the rule/context. Confirmation is not manufactured by the agent. Duplicate
entries for the same run are ignored; different content needs a new ID. New entries start as notes.
The audit reads matching guidance as notes. Retire/remove accepts the reason from the current
maintenance task; it does not require a separate confirmation round. Removal leaves prior run
snapshots unchanged. Remove obsolete seed entries in the skill source during skill maintenance;
ordinary task runs do not rewrite shared seed guidance. The compatibility `guard-due` command only
lists repeated notes; repetition never creates a guard or another review requirement.

If a persistent board helps, use `kanban.py init-db`, `add <id> <title>`, `set-status <id> <status>`,
`get <id>` and `list`. Its default DB is private. An explicit `--db` must also be outside Git and the
skill. It is not required for a small workflow.

## Recipient-host pilot

In an authorized temporary workspace, load this folder through the recipient harness's actual mechanism. Confirm instruction/reference access and command execution. Choose a compliant personal and configuration folder outside every Git ancestor, then run a small real change through configure/audit/record/status/check. Resume in another session and read the saved report. Confirm private records stay outside the project and installed skill. Exercise one blocked receipt or unavailable source and keep the gap visible. If remote issue/PR sources are needed, verify permitted access separately. Local Python checks do not establish universal harness, operating-system or connector compatibility.
