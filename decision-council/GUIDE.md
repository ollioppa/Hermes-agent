# Decision Council: use a structured challenge before deciding

> Documentation of the existing project at `ddac35ef8362d1f93356142ca7f651888f2146e5`, not a new tool or a claim of a successful model run. Source references below are relative to the monorepo.

## Quickstart

- **Purpose:** stress-test an uncertain architecture, plan or root-cause thesis and retain a reasoned verdict, sources and limits.
- **Why not normal chat?** The reusable method separates evidence collection, four blind challenges, a challenge to their shared frame and final synthesis. Two human checkpoints and saved progress make that process inspectable and resumable. A capable chat agent could organize it manually; this project supplies the contract and record coordinator. It does not establish superior model intelligence or guarantee correctness.
- **Good fit:** a consequential decision with plausible alternatives and evidence that deserves adversarial scrutiny. A simple lookup or straightforward known edit is better handled directly.
- **First action:** make `decision-council/SKILL.md` and its references available through the host's supported instruction mechanism, then use the prompt below. No slash command or installation location is assumed.
- **Expected result:** a plain-language verdict and saved `report.md`, including findings, sources, uncertainty and requested/observed model records. “Undecidable” can be a complete result; missing roles cannot.

```text
Question + models → Grounding → YOU review facts
                                   ↓
                        Four mutually blind workers
                                   ↓
                      Outflanker → Chair → Saved verdict
                                               ↓
                                  YOU decide what happens next
```

**Start in the main conversation:**

> Use Decision Council to review this plan: <file>. What could fail, and what evidence would change the decision?

Replace `<file>` with the real plan. Agree scope, thesis/antithesis and explicit available models; choose an authorized private records folder; review the gathered facts before workers start. The canonical introduction is `decision-council/START-HERE.html`; its quickstart and presentation remain the primary user journey. `decision-council/demo.html` is an offline fictional illustration, not a runnable Council session.

## Before starting

Python 3.10+ and the standard library run the coordinator. The host must provide authorized file/tool execution, **seven genuinely independent role contexts**, worker isolation from siblings and main-chat history, and verified binding to the exact models selected by the user. The same model may serve all seven separate contexts. Analysis roles receive complete facts inline and do no new research.

The `tool-model` route needs real per-call model selection. The optional `custom-agent` route is usable only if the host actually discovers the emitted `.agent.md` format and enforces its model/tool restrictions. Neither is a universal adapter. Stop before model work if isolation or binding cannot be established; prompt wording is not model selection. Remote source access requires separately authorized host capabilities.

Records must be outside **every Git ancestor** and outside the package. An ignored directory or a nested repository does not satisfy this boundary. Do not change an unavailable configured root without the user's choice. Personal method lessons are separate from case evidence.

Sources: `decision-council/README.md:18–31`; `decision-council/references/execution-binding.md:7–57`; `decision-council/SKILL.md:18–36`.

## What the agent actually does

The main conversation frames the decision and obtains the first human checkpoint: question, boundary and concrete model roster. Grounding gathers a neutral brief, 3–14 load-bearing sourced facts and coverage of requested sources. Missing sources remain visible; a substantive uncertainty can lead to an undecidable verdict rather than fabricated evidence.

The second checkpoint is **your review of the facts and their uncertainty**, not acceptance of a recommendation. The coordinator binds the actual reply to the factbase digest. Four separate workers then examine the approved factual basis through the selected review type's lenses. A valid no-finding result is useful; it is not a missing worker. The outflanker challenges the strongest claim or common assumption, and the chair explains the mechanism, remaining gap and condition that changes the decision. This is not majority voting.

The Python file does **not** invoke a model or network API. It creates jobs and validates submitted raw responses and metadata. The host dispatches the actual independent calls. Consequently, accepted metadata alone cannot prove truthful sources, genuine approval or an unexposed backend model identity.

Sources: `decision-council/SKILL.md:38–82`; `decision-council/scripts/council_run.py:248–262,336–378,419–493`.

## CLI orientation for the host agent

Commands are the existing interface, not a self-running model pipeline. Paths in angle brackets are placeholders, not values to copy. Run only after the relevant user choices and host checks. Request/envelope syntax is authoritative in `decision-council/references/execution-binding.md`.

```text
python3 decision-council/scripts/council_run.py --help
python3 decision-council/scripts/council_run.py configure --root <approved-private-folder>
python3 decision-council/scripts/council_run.py init --request <approved-request.json>
python3 decision-council/scripts/council_run.py next --run <returned-run-path>
```

`configure` writes the remembered location; `init` writes private run state and returns the full grounding job. This guide does not execute these commands or configure a location. The host must dispatch full jobs and submit actual raw results using the binding reference; do not pass compact metadata to an agent or invent a universal delegation command.

## What is saved, and what completion means

The coordinator retains `state.json`, raw `responses/<role>-<attempt>.json`, `factbase.json`, `factbase.md` and `report.md` within the private run. A requested chair revision preserves prior report/state in `history/`. Report integrity and metadata checks support traceability, not factual truth. Only `complete` establishes workflow completion. Read and deliver the intact report; state incomplete runs as incomplete.

Sources: `decision-council/scripts/council_run.py:419–493,513–525,613–661`; `decision-council/references/execution-binding.md:238–253`.

## Human boundaries and safe recovery

- Reviewing never authorizes edits, deployments, approvals or publication of the reviewed subject. Your two checkpoints must contain real replies, not generated consent.
- After interruption use `next --run <run>`. Recover only missing full prompts with `next --run <run> --role <role>`; repeated role flags recover an independent batch. Do not redispatch already-running siblings just because a compact summary lists pending work.
- Preserve failed returns and incomplete reports. A failed role has at most one retry via `retry --run <run> --role <failed-role>`. A model change needs an explicit user choice and the revised selection record. Never edit digests/state or reset retry limits by starting over without a substantively new question/evidence.
- Changed facts or framing require a new run and fact review. A completed verdict may receive one requested chair-only revision using `revise --run <run> --critique <actual-user-critique>`; a failed revision has no automatic retry.
- After calls finish and continuation no longer needs bindings, `clean-agents --run <run>` removes only unchanged generated agent definitions. Do not delete records as a recovery shortcut.

Sources: `decision-council/SKILL.md:45–76`; `decision-council/references/execution-binding.md:195–253`.

## Read the implementation without mistaking it for a live run

Open the adjacent `walkthrough.html`. Its v2 manifest inventories every runtime Python class/function, the complete module (including constants and CLI dispatch), and instruction authorities. Four worker nodes retain separate identities; harness-role/contract edges differ from artifact and human edges. The fact-review slice traces why workers cannot begin before approval.

This walkthrough is source-only. Synthetic coordinator tests are not real model runs; none were run for this documentation. Recipient-host binding, actual role isolation, authentic human approval and end-to-end operation remain unverified here.
