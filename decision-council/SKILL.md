---
name: decision-council
author: Roland Chotika
description: Stress-test an uncertain architecture, plan, or root-cause thesis with seven independent agent calls, a human fact review and a saved verdict. Use for an explicit council or substantive adversarial decision review; propose available models and let the user choose.
metadata:
  version: "0.6.1-portable-candidate"
license: MIT
---

# Decision Council

Keep the method: **grounding → human fact review → four blind workers → outflanker
→ chair**. Seven real native agent calls, possibly one model in separate contexts.
A simple lookup needs no Decision Council. Reviewing does not authorize changing the subject.
The main chat owns questions and integration; the Python 3.10+ standard-library
coordinator owns jobs, checks and private reports. It makes no model/API calls.

## Frame and choose

1. Reuse supplied context and clarify only material gaps, especially the review
   boundary. Select `architecture`, `planning` or `rca`. Establish question, goal,
   reason for Decision Council, primary sources, success criterion, thesis, meaningful
   antithesis, scope and non-goal; choose the user's response language.
2. Agree a personal folder outside Git and this skill on first use; `configure`
   remembers it and preserves the KB. Keep requests/results there. Read relevant
   [seed guidance](kb/council_kb.md) and personal method lessons, never case facts
   or old verdicts as evidence. For source access or learning, read only the needed
   section of [sources and learning](references/sources-and-knowledge.md).
3. Before model proposals, read [model selection](references/model-selection.md).
   Check actual availability and native binding. Show concrete Economy, Balanced
   and Thorough rosters, recommend one and allow role/lens overrides. Profiles
   retain seven roles. Auto in the main chat does not select explicit role models.

**Checkpoint 1:** show scope, thesis/antithesis and concrete models. Wait for the
user's framing/model choice; reuse an explicit choice already made for this run.
Never manufacture consent or silently replace a model.

## Execute from saved progress

Read [binding: host check and request](references/execution-binding.md#check-the-actual-host-first)
when preparing execution. Resolve the actual native tool and model controls; if they
cannot provide separate contexts and the selected models, explain the limitation
before calls. No simulated returns or prompt-only model selection.

Run `scripts/council_run.py` with the chosen interpreter. `init` starts the approved
request; `next --run <run>` resumes. Newly available stages return full jobs once; intermediate worker submissions and
`next` return compact metadata. Dispatch full jobs unchanged. After interruption,
retrieve missing prompts with `next --run <run> --role <role>`; repeat `--role`
for an independent batch. Never dispatch a metadata-only job.
The binding guide supplies request/envelope syntax; load failure/revision sections
only when needed. Do not reread the full guide on every step.

| Returned status | Main agent action |
| --- | --- |
| `grounding` | Start its native read-only job. It returns a neutral brief without recommendations, 3–14 sourced facts and coverage of every requested source. Evidence gaps belong in that basis; clarification blocks only when a substantive basis cannot be established, not merely when a verdict is uncertain. Submit the actual response; the runner writes the factbase. |
| `awaiting-fact-review` | **Show brief, facts, source coverage and uncertainty; ask for review and wait.** Flag any recommendation in the brief as outside grounding's role, never as a fact. Then `approve-facts` with the exact digest and actual reply. Revised evidence/frame requires a new run. |
| `workers` | Dispatch four separate, mutually blind lens contexts with the complete approved facts and sources. Parallel calls are allowed; submit serially. No research or overall verdict by workers. |
| `outflanker` | After all four valid returns, dispatch its job to challenge the strongest claim/shared frame and propose a falsification check. |
| `chair` | Dispatch the full evidence and prior results. Require mechanism, remaining gap, decision trigger and plain-language walkthrough; undecidable is valid. |
| `failed` | Preserve results and incomplete report. Read binding's failure section; at most one retry per failed role, with explicit choice before changing its model. |
| `complete` | Read the intact saved report, present the chair's brief then verdict and report link, including limits and off-scope findings. |

Use raw structured returns and actual tool metadata. Do not rewrite a failed answer
into a passing one. Analysis roles with `tools: []` need full facts inline; a file path
is insufficient. Keep workers blind to siblings and main-chat history. Accept all
already-dispatched returns even if one fails; never reduce the worker count.

Analysis jobs carry all numbered facts and source coverage, excluding the grounding brief
to avoid carrying a premature recommendation into independent analysis. A worker with no
supported finding returns `lens`, `found: false` and `reason`; it needs no invented claim
or confidence. The runner preserves raw responses and validates any supplied fact references.

`next` revalidates saved integrity. Never edit state/digests to bypass failure or reset
retry limits. A requested chair-only revision uses `revise` once and preserves upstream
work; no automatic retry of that revision. Use `clean-agents` after all calls end and
no continuation needs generated bindings; edited files stay protected.

## Deliver and learn

Only `complete` establishes workflow completion; missing/invalid roles leave a saved
incomplete report. Requested and observed model identities are separate. Checks do
not prove factual truth, reply authenticity or an unexposed backend model.

After delivery offer one optional reflection on Decision Council's method. Save only a
user-supplied or confirmed process improvement with `learn`, using the learning
reference. Case facts, findings, verdicts and domain knowledge stay in run files,
not either KB. Shared seed files remain read-only during use.

[START-HERE.html](START-HERE.html) and
[demo.html](demo.html) explain use. Local tests do not establish live target-environment behavior.
