# Model selection

Read before the framing checkpoint. Choose models for this run, not a permanent
shared roster. Use the actual host/account catalog and delegation controls; a model
in the main picker is not necessarily available to subagents. Record exact names,
check date and availability source. If the agent cannot inspect the catalog, ask
once for the names shown in the user's picker and label them user-reported.
Do not change accounts/settings or infer entitlement from a public catalog.

## Propose and wait

Show three concrete rosters and recommend one with a short reason based on this
question's uncertainty, source complexity, consequences and usage constraints:

| Profile | Allocation |
| --- | --- |
| Economy | Efficient models for bounded work, retaining capable challenge and synthesis |
| Balanced | Reliable grounding/workers; more reasoning for outflanker/chair where useful |
| Thorough | Stronger grounding and analysis where the evidence or consequences justify it |

Name the grounding model, four workers (group identical choices), outflanker and
chair for each. Explain the expected usage/latency trade-off; do not invent prices
or claim seven agents means seven billed requests. If the catalog is small, profiles
may coincide. One model in seven separate contexts is valid; vendor diversity is
optional and is not proof of independence or quality.

Combine model choice with the scope/thesis checkpoint. Wait for the real reply.
“Balanced” accepts the concrete roster just shown. Reuse an explicit choice already
made for this run. Allow any role/lens override; explain concerns without silently
replacing the user's selection. All profiles retain every role and evidence gate.

## Bind and record

Use the actual model argument or a discovered custom agent's model field; see
[binding](execution-binding.md#check-the-actual-host-first). A model name in prompt
text is not binding. The main chat may use Auto, but Decision Council requires explicit role
models. If the user requests Auto for the roles, explain the limit and obtain a
supported explicit roster before dispatch. Never simulate independent agents.

Use the `model_selection` shape in the binding guide. Required fields are `profile`
(economy/balanced/thorough/custom), `confirmed`, `checked_at`, `availability_source`,
`catalog` and `roles` (grounding/workers/outflanker/chair). `worker_overrides` may map
an exact analysis lens to its own assignment. Include `effort` and catalog `efforts`
only when the selected model and tool actually support that control, and record the checked
tool capability as `binding.supports_effort: true`. Without it, omit role `effort` and use
provider defaults. See the binding guide's concrete field example. Custom-agent binding uses
provider-default effort.

Recheck for each new run and after an availability/host/account change. Stored
preferences and aliases do not establish current availability or backend versions.
Keep per-run choices private; persist a preference only when requested. If binding
fails, preserve completed roles and get the user's replacement choice. `retry` can
change only the failed role, within its existing retry allowance.

Report requested model separately from runtime-observed identity. Set observed
identity only from exposed host metadata; an LLM identifying itself is not proof.
Explain missing identity evidence or conflicting names rather than hiding fallback.

