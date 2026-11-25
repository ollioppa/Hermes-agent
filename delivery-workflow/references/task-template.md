# Private task template

The agent fills this in from the request and inspected workspace. Store the resulting task under
the user's personal root. Replace example paths with absolute paths. List only justified exclusions;
optional phases without an exclusion are included automatically. The three required phases remain.

```yaml
---
project_root: /absolute/path/to/workspace
deliverables:
  - src/example.py
  - tests/test_example.py
phases:
  spike:
    decision: excluded
    reason_code: APPROACH_PROVEN
    evidence_ref: /absolute/path/to/prior-experiment.md
  cron:
    decision: excluded
    reason_code: NO_RECURRING_STEP
    evidence_ref: /absolute/path/to/this-task.md
lessons_ack: []
governance_ack: []
---
```

## Outcome

Describe the tool or system to create, or the existing behavior to change, and how the result will
be used and observed. For a new build, name the initial inputs/environment and the intended output.

## Inspected state and sources

Record sample inputs, environment details, source paths, revisions, actual findings, unavailable
sources and remaining uncertainties. State explicitly when this starts as an empty project.
Keep reported requirements separate from inspected code and executed behavior.

## Scope and constraints

Record the requested changes, behavior to preserve, non-goals, handling of existing edits and any
publication instructions already supplied by the user.
When replacing behavior, name the paths to retire and their affected callers across components.
State how each caller switches to the replacement or is removed, including indirect entry points
and fallbacks. If code must temporarily remain, explain why and how access is disabled; do not
leave invalid behavior available as a compatibility route.
For affected validators, gates or guards, state which still protect a current requirement and
which are removed or replaced, with the reason. Keep this in the existing scope; do not introduce
a separate control registry or review cycle.
Record the product/governance LOC baseline, counted paths or mixed-file sections, and counting
method under the [size ceiling](../DESIGN.md#governance-size-ceiling). Budget additions and removals
against the complete project: governance LOC must remain at or below product LOC.

## Plan and phase decisions

Explain the work items, their dependencies and why each excluded phase does not need new work.
Reference the actual supporting evidence. A default reason code alone is not a justification.

## Verification

Name the relevant regression check, direct artifact/runtime check, integration/fallback checks
and what would falsify the proposed solution. Keep a recipient-host test open if it cannot run here.
For replacements, verify that affected entry points use the new path and cannot re-enter the old
one, including relevant error and configuration cases. Record caller disposition and actual results
in the existing integration/verification evidence; keep unresolved reachability visible.
Record the final product and governance LOC totals using the same method. An excess fails
verification; reduce governance without padding the product or silently removing required coverage.
Reuse sufficient checks in the build pipeline. Name the shipping artifact and its ordinary start
command; verify that tests, fixtures and test dependencies are absent from both. Product input
validation remains only where it implements a current functional or security requirement.
