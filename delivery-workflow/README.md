# Delivery Workflow

[User guide](GUIDE.md) · [Technical walkthrough](walkthrough.html) · [Source manifest](walkthrough.json)

Created by Roland Chotika with AI assistance.

A host-agent workflow for delivering working software and substantial changes with saved evidence. The existing Python coordinator manages records, not inference, deployment or autonomous agents. Small known edits normally do not need it.

**Outcome → design/build → actual verification → documented handover**

- Human introduction: [offline guide](START-HERE.html) and [hypothetical example](demo.html).
- Execution authority: [complete agent contract](SKILL.md).
- Commands and payloads: [execution reference](references/execution.md).
- Maintainer contract: [design](DESIGN.md).

## Prerequisites and first use

Use a harness with authorized file read/write, local command execution, evidence retention and session resumption. Load SKILL.md using that host's documented mechanism; no universal discovery path or slash command is assumed. Use Python 3.10+ with PyYAML and jsonschema (`requirements.txt`), plus Git for project inspection. Use the same interpreter throughout. Remote sources and separate reviewers require their own authorized host capabilities; this package supplies neither.

Choose a project folder and user-approved personal/configuration folders **outside every Git ancestor and outside this package**. Ignored directories inside Git are not eligible. Project code stays in the workspace; tasks, receipts, reports, optional board and learning stay private. The configuration default is `~/.config/delivery-workflow/config.json`, or `$XDG_CONFIG_HOME/delivery-workflow/config.json`. See the execution reference for explicit `DELIVERY_WORKFLOW_HOME` / `DELIVERY_WORKFLOW_ROOT` overrides.

```text
<python> -c "import yaml, jsonschema"
<python> <skill>/scripts/arc_run.py configure --root <personal-folder>
<python> <skill>/scripts/arc_run.py audit <personal-task.md> --project <workspace>
<python> <skill>/scripts/arc_run.py record <returned-run-dir> --receipt <receipt.json>
<python> <skill>/scripts/arc_run.py status <returned-run-dir>
<python> <skill>/scripts/arc_run.py check <returned-run-dir>
```

Prepare the private task using [the template](references/task-template.md). Audit returns the next assignment. Execute real work, save its evidence, then record each included phase before proceeding. `status` supports resumption; only a successful final `check` establishes evidence completion. Scripts and record fields retain internal `arc` identifiers to avoid an unnecessary schema/engine rewrite; product and configuration names use Delivery Workflow.

## Safety and limits

The standalone `generate_manifest.py` helper also requires an output location outside every Git ancestor and the distributed package. It creates a new manifest with owner-only permissions and refuses existing destinations or output symlinks; choose a new filename instead of overwriting private evidence.

`configure`, `audit`, `record` and `check` write private state. **`check --dry-run` also writes**; it is a compatibility option, not a write-free preview. The coordinator does not commit, push, deploy, schedule or communicate externally. These actions require their own authorization. A required independent review must be performed by an actual separate reviewer, not inferred from `check`.

Structural evidence validation is not proof of source truth, semantic correctness, actual command execution or publication. Keep missing host/live checks open. A recipient-host pilot is required before claiming compatibility; Python portability alone is not universal harness or operating-system support. No full successful end-to-end run is claimed for this export.

This folder contains runtime files only, no tests, build pipeline, private cases or archives. This sanitized export is licensed under the [MIT License](LICENSE), explicitly authorized by Roland Chotika. Copyright (c) 2026 Roland Chotika. Third-party rights and required notices remain unaffected; dependencies and external data retain their own terms. Private operating data, credentials and unrelated original history are excluded.
