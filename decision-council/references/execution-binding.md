# Independent role execution

This guide is for the main agent running Decision Council. The user chooses the question, boundary and
models in chat; the main agent handles the commands and JSON files. The skill is distributed
independently of any team repository or process.

## Check the actual host first

Requirements: Python 3.10+; file/terminal access for the coordinator; native independent agent calls;
and a verified way to bind the chosen model to each role. No model SDK, API token, package install,
server or daemon is needed. On some Windows hosts the Python command is `py -3`; on others it is
`python` or `python3`. Check the available interpreter and quote paths for the actual shell.

Execution environments expose different delegation tools.
Inspect the current tool schema and custom-agent discovery; do not invent a tool name or argument.
Use one of these bindings:

| Binding | Use when | Actual model control |
| --- | --- | --- |
| `tool-model` | The exposed native delegation tool supports a model argument for this call | Pass the job's exact model through that argument. |
| `custom-agent` | Native delegation can select a discovered custom agent with its own model field | Export personal `.agent.md` files, verify discovery, and invoke the exact returned agent name. |

For `custom-agent`, use a personal agent directory explicitly recognized by the current environment.
This route requires support for the exported `.agent.md` format; it is not a universal installation format. Do not put personal run/model settings in a shared repository. Agent names
include the run, role and attempt to avoid collisions. Analysis agents declare `tools: []` and
`agents: []`; grounding receives only the actual available read/research tools recorded in the
request. Verify the host honors these restrictions. In tool-model mode, apply equivalent controls
when available and ensure analysis agents use no research or further delegation.

Per-call effort is optional: set it only in `tool-model` mode when both tool and model explicitly
support it. Record the checked host capability as `binding.supports_effort: true`, list the
supported values in each relevant catalog entry's `efforts`, and choose one in the role's `effort`.
For example, if the host and model support `medium`, use `"supports_effort": true` in `binding`,
`"efforts": ["medium"]` in that model's catalog entry, and `"effort": "medium"` in its role assignment.
Without that verified capability, omit role `effort`; do not set the flag just to pass validation.
The custom-agent route uses provider-default effort. Do not represent a prompt about
"thinking harder" as a runtime effort setting. Availability in the main model picker does not
establish availability to subagents, particularly across cost tiers or account policies.

If this host cannot bind models or create independent contexts, stop before model work and explain
what is missing. Offer a supported native route or an explicit single-model roster, still with seven
separate agents. Never silently inherit the parent model or simulate agent returns.

Independent calls must receive all required context in their job, not inherited chat history or sibling results. The main conversation owns both human checkpoints. Check whether the environment honors tool/delegation restrictions, exact model selection and account limits. Do not silently fall back. A host-specific installation or UI command is not part of this package's contract.

## Personal location and request

On first use, agree the location with the user and run:

```text
python3 <skill>/scripts/council_run.py configure --root <personal-folder>
```

The folder must be outside Git repositories and the distributed skill. The location pointer is
`~/.config/council/location.json` on macOS/Linux or `%APPDATA%/council/location.json` on Windows.
The existing personal `council_kb.md` is preserved. There are no personal files in the skill itself.
`init --root ...` can use a specific personal root without changing the remembered preference.

Save the approved request under the personal root. This example uses **placeholder models and tool
names**, not a catalog to copy. Replace every placeholder with current, checked values. Fields and
outputs may use the user's preferred language. The `framing_reply` is the user's real response to
the displayed scope and concrete roster, not a generated consent statement.

```json
{
  "question": "The decision to evaluate",
  "goal": "What the user wants to achieve",
  "why_council": "The meaningful uncertainty",
  "primary_sources": "Concrete local paths, URLs or supplied evidence",
  "success_criterion": "What would settle this decision",
  "thesis": "The proposed answer",
  "antithesis": "A meaningfully competing answer",
  "scope": "The agreed level and boundary",
  "non_goal": "What this decision does not address",
  "analysis_type": "architecture",
  "language": "English",
  "framing_reply": "The actual user reply",
  "binding": {
    "mode": "custom-agent",
    "host": "Actual execution environment and version",
    "verified_by": "Observed native tool schema and custom-agent discovery",
    "grounding_tools": ["ACTUAL_READ_TOOL", "ACTUAL_RESEARCH_TOOL"]
  },
  "model_selection": {
    "profile": "balanced",
    "confirmed": true,
    "checked_at": "Actual check date/time",
    "availability_source": "Observed tool result or user-reported model picker",
    "catalog": [{"model": "EXACT_MODEL_A"}, {"model": "EXACT_MODEL_B"}],
    "roles": {
      "grounding": {"model": "EXACT_MODEL_A"},
      "workers": {"model": "EXACT_MODEL_A"},
      "outflanker": {"model": "EXACT_MODEL_B"},
      "chair": {"model": "EXACT_MODEL_B"}
    },
    "worker_overrides": {}
  }
}
```

See [model selection](model-selection.md) for per-lens overrides and optional supported effort.
Do not retain secrets or unnecessary source content in availability evidence.
For workspace, IssueTracker and CodeReview reviews, also include `source_targets` from
[sources and skill learning](sources-and-knowledge.md). Add relevant Decision Council method improvements from the personal KB as
`skill_lessons` with `purpose: skill_improvement`. Both are assembled by the main conversation, not by the user. Ensure grounding can
access the required read tools or an attributed private source packet before initializing the run.

## Initialize and invoke jobs

```text
python3 <skill>/scripts/council_run.py init --request <request.json>
python3 <skill>/scripts/council_run.py next --run <returned-run-path>
```

`init` returns an absolute `run` path and the full grounding job. Keep the path.
`approve-facts` returns the four full worker jobs; finishing the last worker returns
the outflanker, then its submission returns the chair. Intermediate worker submissions
return metadata only, so sibling prompts are not repeated. `next` is compact by default.
After interruption, fetch only missing full prompts for dispatch:

```text
python3 <skill>/scripts/council_run.py next --run <run> --role grounding
python3 <skill>/scripts/council_run.py next --run <run> --role <lens-1> --role <lens-2> --role <lens-3> --role <lens-4>
```

Only currently pending roles can be fetched; workers remain unavailable before fact review.
Each fetched job retains the complete approved facts and source coverage. Dispatch the fetched
batch once; intermediate submission summaries are not instructions to re-launch siblings.
Do not pass a metadata-only job to an agent. With `custom-agent`, export bindings before calls:

```text
python3 <skill>/scripts/council_run.py export-agents --run <run> --directory <personal-agent-directory>
```

Verify the host discovered those exact agents, model fields and tool restrictions. Some hosts may
need an agent-list refresh; exporting a file alone is not proof of discovery. Do not invoke a generic
agent while claiming it used an exported definition. Re-export after a retry or chair revision;
only pending roles are exported and a new attempt gets a distinct name.

Each job includes `role`, `attempt`, `model`, optional `effort`, `binding_mode`, `agent_name`, `tools`
and the complete `prompt`. Invoke the actual native tool in an independent context with the full
prompt and either the explicit model argument or exact custom-agent name. Do not pass sibling
worker results or the main conversation history. Parallel worker calls are allowed; coordinator
writes must be serial. Wait for the real result of each native call.

## Submit actual returns

Save an envelope containing the actual host/tool invocation metadata and the agent's raw JSON:

```json
{
  "execution": {
    "call_id": "Unique identifier from the actual native call",
    "binding_mode": "custom-agent",
    "requested_model": "EXACT_MODEL_A",
    "agent_name": "Exact name returned in the job",
    "observed_model": null
  },
  "output": {"is_clarification": false, "brief": "Actual agent brief", "facts": []}
}
```

The empty `facts` array above only illustrates the envelope; real grounding requires 3–14 facts.
Every job prompt specifies that role's output schema. Do not repair or substitute an agent's answer
in the main chat to pass validation. If it returns malformed JSON, preserve the raw text in `output`
and let validation fail. For a failed call, use `output: null` and `error` with the real error text.
Do not fabricate a call when no native invocation occurred.

Workers use two response forms. A positive finding needs the complete finding fields in its
job. A no-finding response needs only `lens`, `found: false` and a nonempty `reason`; optional
`sources` must cite existing fact IDs, and `claim` must be absent or empty. Do not add confidence
or a claim to a raw no-finding return. The coordinator records all four responses and passes
the absence of findings to synthesis without treating it as a missing worker.

In `tool-model` mode omit `agent_name`; include `requested_effort` only if the job specifies it.
`observed_model` is optional or null. Add it, with `model_evidence`, only when actual host metadata
identifies the executed model. An agent's self-description is not evidence. If the observed name
conflicts with the selected name, validation stops: resolve alias/version mapping or a changed
assignment with the user before a retry. Never hide a fallback as the original model.

```text
python3 <skill>/scripts/council_run.py submit --run <run> --role <job-role> --response <response.json>
```

Commands emit JSON. Exit code 2 means an error or failed run, not completion. A pending worker from
an already-dispatched batch may still be submitted after a sibling fails; the overall run remains
failed until the issue is resolved. No outflanker or chair is dispatched from that failed state.

At `awaiting-fact-review`, show the returned brief, facts, `source_coverage` and uncertainty. After the user's
real acceptance of those exact facts:

```text
python3 <skill>/scripts/council_run.py approve-facts --run <run> --digest <returned-digest> --reply <actual-reply>
```

The four full jobs are returned once. Dispatch that batch and submit each actual result
serially; the last valid return supplies the next stage. Use `next --role` only to retrieve
a missing pending prompt after interruption. A retry returns only the retried job once
all failures are resolved; recover any other missing pending jobs with `next --role`.
Quote user text safely for the shell; never interpolate unescaped text into executable commands.

## Failures, retries and a requested revision

`next` is read-only and reconstructs pending work from persisted state. Do not rerun completed
roles. A `.lock` means another write may be active; inspect the process before removing a stale
lock. Do not edit `state.json`, receipts, factbase or report to bypass validation. Keep annotations
in a separate file. Interrupted writes or changed digests need inspection before continuation.

A failed role has one retry with its selected model:

```text
python3 <skill>/scripts/council_run.py retry --run <run> --role <failed-role>
```

If a model became unavailable, propose a replacement and get the user's choice. Save the full
revised `model_selection` record, changing only that failed role (use `worker_overrides` for one
worker), then:

```text
python3 <skill>/scripts/council_run.py retry --run <run> --role <failed-role> --selection <selection.json> --reply <actual-choice>
```

It consumes the same single retry allowance; completed roles and their evidence stay intact.
Do not initialize a fresh run solely to reset retry limits. New evidence or a changed question
warrants a new run with a fresh framing and fact review.

After a completed verdict, the user may request one chair-only revision:

```text
python3 <skill>/scripts/council_run.py revise --run <run> --critique <actual-user-critique>
```

This archives the earlier report/state under `history/`, retains all upstream results, and returns
one full chair job. A failed revision has no further retry. Model changes are not part
of this command.
Re-export the pending custom agent if applicable. An additional review with new evidence is a new run.

## Deliver, then remove temporary bindings

Only `complete` means all seven roles and the current chair verdict passed validation. Read the
saved report; deliver its plain-language brief first, then the verdict and report link. The report
contains all worker results, original sources, uncertainty and requested/observed models. Failed
runs remain available as explicitly incomplete reports. An earlier successful report remains linked
when a later requested revision fails.

When all calls have ended and their definitions are no longer needed:

```text
python3 <skill>/scripts/council_run.py clean-agents --run <run>
```

Only unchanged generated definitions are removed. Edited definitions are preserved. Reports,
responses, facts, model choices and personal lessons remain under the user's personal root.

Save a user-supplied or confirmed improvement to Decision Council's method with `learn --run <run> --entry <lesson.json>` using the
[learning contract](sources-and-knowledge.md#save-a-confirmed-lesson). This is a separate optional
step after delivery. The KB never stores case facts, findings, verdicts or project knowledge.
The actual confirmation stays in the run's learning receipt. Read relevant method improvements
before the next run and pass their context and limits through `skill_lessons`, separately from evidence.

## Verification boundary

Run the portable behavior suite without model-account credentials:

```text
python3 -m unittest discover -s <skill>/tests -p 'test_*.py' -v
```

These tests use synthetic agent responses and verify state, model contracts, sources and saved
artifacts. They do not establish live compatibility for every host/version or organization.
Before broad distribution, run one real Decision Council on the intended host: confirm discovery/model
binding, both human checkpoints, four isolated worker calls, full-source handoff, persisted report
and a clear failure for an unavailable model. These export candidates have not completed that live check.
