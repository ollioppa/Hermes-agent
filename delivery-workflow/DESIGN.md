# Delivery Workflow — Design

This document defines the exported method and coordinator contract, not proof of recipient-host compatibility.

## Governance size ceiling

The hard limit is **G <= P**: governance code must never exceed productive code in lines of code.
This is a ceiling, not a target. Count the whole maintained target project, including existing
controls and project-specific code stored outside its repository, rather than only the current diff.

- **P — product:** maintained first-party code that implements the requested product behavior,
  including necessary input validation and authorization. Dead, disabled, duplicate, generated
  or vendored code cannot inflate P. For Delivery Workflow itself, its requested coordinator and receipt
  validation are product behavior; checks supervising that implementation belong to G.
- **G — governance:** first-party tests, executable fixtures, check helpers, meta-validators,
  gates/guards supervising development, custom verification/build orchestration and executable
  control configuration. Count their project-specific wrappers or extensions wherever stored,
  including temporary check code. Shared installed tools and third-party libraries count on
  neither side; project-specific additions still count. Classify mixed files by purpose.
- Count physical source lines containing code with the same language-aware method on both sides;
  exclude blank and comment-only lines, prose and inert data. Count maintained sources once,
  not generated/minified copies. Record the command/method and counted paths or sections in the
  existing task/verification evidence. Do not minify, pad or relabel code to alter the ratio.

Establish the baseline during understanding. Check the projected totals before adding governance
or deleting product code, and recount after the change in existing verification. If P is zero,
G must also be zero: use existing tools and build a meaningful product slice before custom test or
validator scaffolding. Phase ordering does not authorize exceeding the limit. An inherited excess
requires reducing/consolidating governance first, not grandfathering it. Preserve required behavior
and protection while simplifying; if that cannot fit, keep the work incomplete and state the
conflict. Never silently weaken required checks or grow product code merely to satisfy the ratio.

Reuse an available counter or a small build-time measurement, without adding a permanent metering
framework or another governance phase. Record a failed existing verify check for G > P; it cannot
be accepted as complete. The agent owns classification and measurement; the runner rejects failed
recorded checks but does not infer code purpose or independently audit these totals.

## Retiring replaced paths and obsolete controls

A replacement is complete only when the intended new behavior works and the superseded behavior
is no longer reachable from any affected component. Before editing, trace callers and entry points
across the project, including indirect dispatch, configuration, scheduled jobs and error/fallback
branches where relevant. A local implementation swap is insufficient if another consumer still
selects the old path. Remove obsolete code and its references together; regenerate affected shipped
copies. If deletion cannot yet happen, disconnect every affected entry point and record the concrete
reason and remaining cleanup. A flag defaulting to off is insufficient if it can re-enable invalid
behavior. Do not retain invalid behavior as a compatibility fallback or add a governance wrapper
around it. An intentionally supported migration path needs an explicit current design contract;
it cannot silently preserve behavior the new requirement makes invalid.

Use the existing integration and verify phases to check both directions: affected callers reach
the replacement, and normal execution, failure handling and relevant alternate configurations
cannot reach the retired implementation. Search results help locate callers but do not establish
dynamic reachability by themselves. Exercise affected entry points against the built artifact in
the build pipeline. An inaccessible affected consumer leaves retirement unverified; report the gap.
Record caller disposition, observed checks and remaining limitations in existing task/phase evidence
and update the maintained design. No new phase, governance module, runtime self-test or global
retirement registry is introduced. Receipt validation checks evidence references; the agent remains
responsible for tracing consumers and judging whether the executed checks establish retirement.

Governance is maintained by removal as well as addition. For controls affected by the requested
work, the agent determines which current requirement each validator, gate or guard protects. It
must delete obsolete, superseded, duplicate or inapplicable controls and their active callers,
pipeline hooks and stale documentation. Historical existence is not a retention criterion. State
the reason in the existing task/design or closeout; do not introduce another registry, approval
loop or governance layer. A failed valid check still calls for a fix. A demonstrably obsolete
requirement calls for removal or replacement of its control, not permanent exceptions around it.

## Separating build from operation

Tests, fixtures, test runners and test-only dependencies exist in the development/build pipeline,
never in shipped application modules, imports or startup paths. Check the actual artifact and its
ordinary entry point in the build/acceptance pipeline. Keep necessary product input validation or
authorization only while it implements a current requirement. The skill's functional receipt
validation is part of the build tool; it must not be embedded in the application it creates.

Reuse sufficient existing build coverage. `EXISTING_BUILD_COVERAGE` allows constraints/tdd to be
excluded with a reference to the existing checks, which must run in verification. There is no need
to invent a red test, a second validator or another framework just to populate a phase. New tests
need an uncovered behavior or relevant failure to justify them. Once the agreed checks pass,
delivery does not require further test expansion, a lesson or a review of the governance itself.

Historical run records can remain without keeping their old product controls alive. Snapshot
files needed as evidence in the current run before an intentional deletion and cite those private
copies. Never rewrite earlier observed results. A later attempt to revalidate an old run can report
missing historical paths; that does not require restoring obsolete active code.

Personal method rules can be retired or physically removed with `lessons.py retire/remove --reason`.
Removal edits the personal registry and leaves earlier run snapshots intact. Packaged obsolete
rules are removed from the skill source during its maintenance, not kept as permanent active
legacy obligations. Ordinary task runs use seed guidance read-only and can mark it inapplicable.
Keyword matches are advisory only; explicitly selected checks still bind their current run. A
reasoned `not_applicable` lesson acknowledgment resolves the suggestion without a blocking flag.
An `applied` guidance acknowledgment needs no extra proof artifact; selected phase receipts already
record the actual work.

## Execution and authorization

The host agent inspects, plans, edits and executes. Python deterministically creates the manifest,
checks receipts and records progress. There is no model API, fixed model roster or separate router.
Use the model selected in the host. Optional delegated work must follow the host and user policy.
independent deliberation and requirements discovery can provide inputs but are not dependencies or automatic approval stations.

A scoped implementation request runs through the applicable phases without repeated confirmation.
A material unknown or permission boundary still needs the user's input. Scheduled jobs, deployment,
communication, commits and pushes require the authority appropriate to the requested work. `check`
performs read-only Git inspection and writes only private status files. It never publishes anything.

## Personal state and project identity

On first use the user supplies one root outside Git and the installed skill. `configure --root`
stores a pointer in `$XDG_CONFIG_HOME/delivery-workflow/config.json`, defaulting to
`~/.config/delivery-workflow/config.json`. `DELIVERY_WORKFLOW_HOME` can explicitly override it for an isolated run;
`DELIVERY_WORKFLOW_ROOT` is an alternate variable for the personal root, never the code/config root.
Commands that write state require a configured root. Read-only manifest validation may use only
the seed registry when no personal root exists.

```
<personal-root>/
  tasks/<case>/task.md
  arc_runs/<run-id>/
    run.json
    preflight_result.json
    manifest.yaml
    audit_result.json
    lessons_snapshot.yaml
    ledger.jsonl
    receipts/<phase>.json
    report.md
    check_result.json
    <evidence files and optional learning confirmations>
  lessons.yaml
  kanban.db                 optional
```

Run IDs retain `arc_YYYYMMDD_HHMMSS_<four random hex digits>`; exclusive directory creation rejects
collisions. The private task lives outside the repository. Its explicit `project_root` or `--project`
argument identifies the workspace for preflight and Git closeout. For a new build, the host creates
the requested empty project directory before audit; pre-existing software or Git history is not
required. These identities must not be inferred from the installed skill location or the private
task's parent directory.

Resolved write destinations are checked against their owning folder, Git repositories and the
skill. A symlink into another folder or Git repository is rejected. Configuration preserves an
existing personal registry. Runs bind their stored home and cannot be silently resumed under
another root. Per-run exclusive locks serialize mutations; atomic replacement protects individual
files. A crash between receipt and ledger writes requires explicit inspection. This is protection
against accidental redirection and drift, not a security boundary against a malicious local process.

## Phases and evidence

| Phase | Plain-language action and benefit | When used | Evidence |
| --- | --- | --- | --- |
| understand | Agree on the goal: identify missing requirements and establish the behavior the user needs before choosing an approach. | Always | Requirements, inspected inputs/environment, unresolved choices, preflight and existing implementation when present |
| spike | Try the uncertain part: test a risky assumption before building around it. | When the approach is not yet supported by evidence | Experiment result: VALIDATED, PARTIAL or INVALIDATED |
| plan | Choose the design and build order: create or reuse the project design and arrange dependent work. | When no adequate current design and build plan exist | Design decisions, scope, non-goals, dependencies and observable success criteria |
| constraints | Define valid output: turn important output rules into checks that catch misleading results. | When output rules need new verification coverage | Reused or new build check with observed accepting and rejecting cases |
| tdd | Build the working parts: implement behavior and use focused checks to catch errors during construction. | When new test evidence is needed; reuse sufficient existing coverage | Actual failing and passing runs and the relevant suite result |
| integration | Make the parts work together: connect affected callers and retire replaced paths so the whole flow uses the intended implementation. | When components must connect or an existing route is replaced | End-to-end behavior, failure handling and evidence against re-entry into retired paths |
| cron | Set up automatic runs: arrange requested repetition and verify that it produces the intended result within authorized scope. | Only when recurring execution is requested | Schedule and an actual first-run artifact |
| doc | Explain use and upkeep: preserve current instructions and design decisions for the next user or maintainer. | When usage or design is new or changed | Maintained design and usage instructions |
| verify | Check the complete result: exercise the assembled deliverable in a suitable setting; keep any agreed live check open until authorized and run. | Always | Direct artifact/workflow checks, relevant failure cases and the governance size measurement |
| postmortem | Hand over and finish: deliver a usable result with a clear record of checks, limits and cleanup. | Always | Outcome, usage, gaps, retired paths/controls and retained evidence; learning is optional |

Phases appear exactly once in catalog order. `understand`, `verify` and `postmortem` cannot be
excluded. Allowed reasons live in `config/exclusion_rules.yaml`: APPROACH_PROVEN, PLAN_EXISTS,
NO_CODE, NO_OUTPUT_CONTRACT, NO_INTEGRATION_POINT, NO_RECURRING_STEP, NO_CANONICAL_DOC
and EXISTING_BUILD_COVERAGE (for constraints/tdd).
OPERATOR_ASSERTED remains flagged; it is not an override that makes unsupported claims true.
Exclusions need a cited existing file. The agent judges whether its content actually justifies the
reason; a path check cannot do that. The generator retains deliverables so NO_CODE can be checked
against executable file types. Optional phase choices should be proportional to the task.

## Audit, recording and closeout

`audit` saves an incomplete report before preflight, generates a manifest, validates it and records
the actual audit event. It binds the manifest, task, preflight and lesson snapshot by SHA-256.
The snapshot records which seed/personal method lessons were available at audit time. Keywords
match the task body, excluding YAML administration, so a phase named `cron` does not trigger a
scheduled-work review by itself. A missing schema dependency is visible and cannot approve a run.

`record` accepts only the next included phase in an approved run, validates its identity and
manifest-bound governance, checks prior receipts again, and stores the receipt digest in the ledger.
An INVALIDATED spike is saved as a stopped run; no downstream phase or complete check is allowed.
There is no API for manufacturing a completed phase from a prose assertion alone.

`check` validates all included receipts, their digests, required evidence paths and ledger order.
It rejects altered task/manifest/audit bindings and missing, duplicate, out-of-order or wrongly
identified phase events. Governance warnings stay in the report. Success saves `check_result.json`,
updates `report.md` and records completion. `status` recovers progress without claiming that old
checks still pass. Re-running `check` is required to verify the current evidence.

Evidence completion and publication are separate: `complete` means the recorded evidence passed.
Git state is reported as `working-changes`, `clean`, `no-git` or an error, with the observed HEAD.
Working changes are valid delivery for a user who requested edits without a commit. A clean worktree
is not proof of a push. Publication remains `not-checked`; the host separately reports any authorized
commit, push or deployment. A missing workspace or Git inspection failure cannot become `no-git`.

The optional SQLite board stores personal task IDs/statuses with a busy timeout. Plan/postmortem
receipts can reference it; the postmortem validator requires referenced tasks to be done. The board
is never required for a small workflow and a Markdown board is not a substitute for a claimed DB check.

## Conditional governance

The registry in `config/governance_modules.yaml` suggests three possible checks from task content:
consumer mapping for changed callers/scheduled/report paths; quality regression against an existing
anchor; and input validation before an expensive reasoning pipeline. Keyword matches create advisory annotations only, without requiring acknowledgment. The agent
explicitly includes a module only when the current task needs it, or records a reason it does not apply. Pipeline acknowledgment names its planned validator and output;
verification requires a passing validator result dated before reasoning began. Consumer evidence
includes actual search output and a Hardcoding column. Missing quality anchors remain visible
warnings with a proposed location. These checks do not automatically require a independent deliberation or network call.

## Knowledge and sources

The packaged KB and sanitized seed registry contain reusable method guidance, never historical
user runs. Personal `lessons.yaml` contains only user-confirmed improvements to Delivery Workflow's method,
with context, limits, narrow trigger and originating run IDs. Case details and the confirmation
reply stay in the run. `learn` rejects result fields and requires `purpose: skill_improvement`;
semantic review of the text remains the main agent's responsibility. No automatic global memory
writes occur. Repeated lessons never automatically become guards, mandatory reviews or scheduled work.

Inspect local code and canonical documentation first. Read specifically relevant issue tickets or
pull requests through available authenticated tools, retaining source IDs/revisions and coverage
gaps in the task/evidence. A missing connector is reported rather than replaced with an invented
finding. The coordinator has no credentials and does not fetch or send network data.

## Validation and limits

Meaningful regression coverage must include a complete command-line run from a copied skill folder,
interruption/resumption, private path redirection, receipt identity/order, altered task/manifest,
failed or missing live checks, project identity and personal learning persistence. Keep synthetic
fixtures distinguishable from live project evidence. Run the validator suite with the same interpreter
used by the runner. Follow [the command reference](references/execution.md) for a recipient-host pilot.

Structural checks cannot prove source truth, that an agent really ran a claimed command, or quality
on a different model/host. Receipt digests detect accidental edits, not forged evidence. Existing
evidence files are checked for presence; their arbitrary contents are not all cryptographically
bound. Harness discovery, recipient permissions, operating-system behavior and authorized remote-source access remain pilot checks. The demo is hypothetical, runs offline and saves nothing.
