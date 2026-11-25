# Decision Council skill learning

Read before framing. This KB improves how Decision Council works. It contains no case results, verdicts or
project knowledge. This packaged guidance is read-only during normal runs. User-confirmed method
improvements belong in the user's separate `council_kb.md` under their Decision Council output folder.

## Framing traps

- For a design proposal with no code yet, decide whether the mechanism alone or its future call sites are under review.
- For a component inside a larger system, ask whether surrounding behavior is in scope.
- For root-cause analysis, bound how far back the causal search should go; an upstream truth may be unactionable.
- For plan review, distinguish the sequencing of work from the content of the plan.
- If thesis and antithesis say the same thing, sharpen the decision before starting a council.
- If a question says “look at everything,” ask which decision the user needs to make.

## Lessons

- Pass scope and non-goal to every downstream seat. The chair should route findings that answer a different question to an off-scope appendix.
- Let the outflanker question the frame freely. A wider finding belongs in the verdict when it changes the answer to the asked question.
- Show a plain-language brief before the fact table so the human can review the actual dispute.
- Make the verdict understandable with a concrete walkthrough of the normal and failing cases when the mechanism is dense.
- Ask a framing question before drafting the user's frame. Approval of a prewritten frame can conceal a mistaken scope.
- Keep the factbase to the facts that could change the decision; repeated background facts add cost without signal.
- Distinguish intended behavior in a ticket or PR description from inspected code and executed checks.
- Match workspace and PR revisions before using local code as PR evidence; show mismatches and access gaps.

After a run, optionally record method improvements provided or confirmed by the user in their KB.
Include their context and limits. Keep the review's outcomes in its report. Updating this
packaged guidance is separate skill maintenance, not an automatic side effect of using Decision Council.
