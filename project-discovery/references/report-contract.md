# Discovery report contract

Produce a discovery report after every run and save it under the user's configured private root, or at a different report path they explicitly gave for this run. Choose the format from the request, not from whether an IssueTracker ticket exists. Both formats separate what was learned from what remains unknown. Do not invent fields merely to complete a template. A Ready status is a handoff assessment, never execution approval. The report is complete only after the file is written successfully; if writing fails, tell the user and retain the text for a new destination. A personal KB update is a separate, optional step after the report.

## General-question report

Use this compact form for personal or general questions. **Answer the question in the report**; do not replace the answer with a plan to investigate. A Ready/Draft or rollout status is not relevant unless the user asks for a project decision.

```markdown
# Discovery Report: <user's question>

## Answer
<specific answer tailored to the clarified need; distinguish advice from facts about the user's environment>

## What clarified the question
- <the user answer or source that materially shaped the answer; omit a list of every question asked>

## Basis and limits
- <user-provided context and any sources actually checked>
- <important assumption or unknown that limits the answer, if any>

## Open point
- <only a question that would materially change the answer; omit this heading if none>
```

## Task or spike report

Keep the main headings below; omit “What discovery changed” if no material change occurred. Omit irrelevant details inside a heading, never invent them. A report may be useful while still marked **Draft**. The same structure works with only user answers, with ticket/workspace evidence, or with both.

```markdown
# Discovery: <question, spike, or task>
Status: Draft | Ready

## Basis
- <Relevant user answers and assumptions. Add ticket, workspace, documentation, tests, or live checks only when actually used. For a source-free inquiry, say once that no task-specific source was supplied or needed.>

## Outcome and acceptance
- Goal: <desired outcome or decision and why, or Open>
- Deliverable: <specific artifact or investigation result and intended reader, or Open>
- Checks: <observable success or decision criteria; mark each Confirmed, Proposed, or Open>

## What discovery changed
- <initial assumption or option → clarified answer → effect on scope, risk, or plan; omit if no material change>

## Scope and current state
- Included: <explicit targets, or Open>
- Excluded: <only exclusions actually agreed; otherwise Open>
- Current: <what is reported, inspected, or still unknown; do not imply a current system exists when none was supplied>
- Gap or uncertainty: <specific obstacle, decision, or hypothesis to investigate; do not imply that implementation is always needed>

## Constraints and risks
- <confirmed deadline, owner, dependency, or compatibility constraint; otherwise Open or omit if irrelevant>
- <risk → impact → proposed mitigation or verification>

## Approach and validation
1. <first executable or investigative step and expected output, if action is needed>
2. <next material step, if needed>
- Validation: <how to check the result or make the intended decision; for a purely explanatory answer, state its practical limits>

## Open decisions
- <open question → decision it affects → who or what can resolve it>
```

Use natural phrasing and avoid mechanical status tags on every sentence when grouping is unambiguous. Do not label a whole section “confirmed” if it includes suggestions.

For a source-free inquiry, avoid an empty checklist of “Ticket: unavailable / Workspace: unavailable / Checks: not run.” Record the user-provided basis, assumptions, and what has not been checked once. A spike can be **Ready for investigation** with a defined question, output, decision criteria, and first check, while remaining unready for implementation.
