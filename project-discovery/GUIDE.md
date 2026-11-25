# Project Discovery — user guide

## Quickstart: clarify before committing to work

- **Benefit:** turn an uncertain question into a saved answer or usable task/spike handoff. The contribution is adaptive clarification and an explicit evidence boundary, not automatic implementation or a prescribed team of agents.
- **Fit:** use when the outcome, scope, acceptance criteria or approach is unclear. An ordinary direct answer is sufficient when the request is already clear.
- **Need:** an agent with dialogue, access to authorized sources and verified private file writes. Python 3.10+ enables the supplied storage helper; equivalent file tools are supported. No ticket system or repository is required for a general question.
- **Start:** make `project-discovery/SKILL.md` and its relative references available to your agent, then ask: “Use Project Discovery to clarify this question: …”. This is an example starter request, not a recorded run or special slash command.
- **Expect:** an actual saved report, its path and a brief answer/handoff. A task may be Draft or Ready; a general answer needs no artificial readiness status.

```text
Authorized sources → material question ⇄ your answer
                                      ↓
                              answer or handoff
                                      ↓
                              verified private save
                                      ↓
                         optional confirmed lesson
```

On first use, the agent asks where to keep personal Discovery files **and waits**. Choose a private location, preferably outside repositories. This storage choice is separate from clarifying the task. The shared package remains read-only.

## What happens after you start

The agent reads relevant supplied sources before asking you to repeat available facts. It asks one concrete question when different answers would change the result, waits for your reply, and adapts the next question. Goal, success, scope, current state, gap, constraints and approach are internal perspectives—not seven mandatory questions. Relevant private lessons can suggest questions but cannot establish current facts.

You can request an early draft or decline further questions. Unresolved material decisions then remain visible; they must not be silently replaced by assumptions. Extensive inputs may justify bounded read-only delegation, but the main agent owns the conversation and synthesis.

For a general question, the report must actually answer it. For a task or spike, it records outcome and acceptance, scope/current state, constraints/risks, approach/validation and open decisions. **Ready means sufficiently clear for the next step, not authorized to implement or deploy.** Grounded facts, proposals and open questions remain distinguishable.

After saving, the agent returns the actual path. An optional reflection can add a reusable lesson to your private knowledge base only when you supply or confirm it. Skipping reflection does not make the report incomplete. On resumption, reuse the existing report and confirmed answers rather than restarting.

## Recognize success—and recover safely

| Situation | Expected response |
| --- | --- |
| No configured location | Ask for your private folder and wait; do not select one silently. |
| Configured root unavailable | Ask for an accessible location. Do not silently relocate the private KB. |
| File already exists | Preserve it; choose another name, or overwrite only with explicit permission. |
| Save fails | Keep the draft and request an accessible destination. A failed write is not a saved report. |
| Python or pointer persistence unavailable | Use equivalent file tools with the same privacy, layout and overwrite rules; verify the write. Explain if the next session must ask again. |
| Evidence unavailable or conflicting | Label the affected claim and its consequence. Do not present an assumption as checked fact. |

The helper checks storage, not whether the answer is true or the task is Ready. Even an explicit one-run output requires configured personal storage in the current implementation; it changes the report destination, not the KB root (`scripts/storage.py:85-103`).

## Boundaries and deeper reading

No implementation, ticket edits, unsolicited project, automatic publication or shared-KB update is authorized by discovery. Private reports, personal KB entries and credentials do not belong in this exported package. This guide describes source behavior; no target conversation, storage operation or production write was performed to produce it.

The adjacent [walkthrough](walkthrough.html) connects the real storage functions with instructed dialogue and human decisions. The [manifest](walkthrough.json) records the source inventory and evidence limits. Embedded source paths are relative to the repository; documentation is bound to commit `ddac35ef8362d1f93356142ca7f651888f2146e5`.

### Source map

- Purpose, fit, capabilities: `project-discovery/README.md:5-27`.
- First use, adaptive dialogue, permissions, resumption: `project-discovery/SKILL.md:10-85`.
- Question selection: `project-discovery/references/question-playbook.md:3-24`; generic prompts: `project-discovery/kb/discovery_kb.md`.
- Output and readiness: `project-discovery/references/report-contract.md:3-66`.
- Recovery, private layout and reflection: `project-discovery/references/storage.md:7-57`.
- Actual persistence behavior: `project-discovery/scripts/storage.py:12-125`.
