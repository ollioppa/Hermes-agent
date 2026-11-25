# Shared discovery question guide (read-only)

Use only the prompts relevant to the task. These are general question prompts; no ticket history belongs in this shared file.

## Across task types

- Establish the actual deliverable and its reader. For a recurring report or handoff, ask for an earlier accepted example; format continuity can be part of success.
- For time-bound deliverables, learn the real deadline before expanding the investigation.
- Replace vague outcomes such as “looks good” with an observable acceptance check. Verify that the data needed to measure it exists.
- Name the affected systems, users, files, or environments. Do not infer “everything” from a broad ticket title.
- Distinguish a user recollection, ticket claim, archived snapshot, current source, and direct observation. Verify changing status against the live source when available.
- Treat a symptom, a plausible cause, and a confirmed cause as different claims. Ask what evidence would separate competing explanations.
- Check whether the declared ticket type matches the expected deliverable. A spike, implementation, and production rollout have different completion conditions.
- For a general question, ask only the follow-ups needed to understand it, then answer that question rather than proposing a project. For an explicit spike, identify the decision the exploration should enable, compare plausible options, and propose the cheapest check of a decisive assumption. A ticket, repository, and pre-existing system are optional.
- Trace dependencies and consumers beyond the named component. A copied directory or single repo may omit tests, callers, configuration, or deployment state.
- For an existing plan, identify the step that satisfies the actual requirement and test the plan's premises before endorsing it.
- An absent artifact can be a useful finding: identify the first missing link in the expected delivery chain.
- “Verified” requires a check of the relevant target and scope. Record what was actually run and what remains untested.

## By task type

- **Audit or review:** exact targets, evidence standard, output format, intended reader, and approval path.
- **Migration or port:** actual source contract, target-environment differences, dependent callers, compatibility, validation, and recovery.
- **Implementation or integration:** affected interfaces, other consumers, failure behavior, acceptance checks, and ownership.
- **Refactor:** behavior to preserve, copies and callers, and a before/after comparison.
- **Fix or RCA:** observed failure, reproduction or timestamps, affected path, alternative causes, and a regression check. A recovery action alone does not prove the cause.
- **Deployment:** rollout order, monitoring, downtime, rollback trigger, and who can execute recovery.
- **Documentation or handoff:** target audience, verified current commands and values, missing knowledge, and a realistic end-to-end walkthrough.
