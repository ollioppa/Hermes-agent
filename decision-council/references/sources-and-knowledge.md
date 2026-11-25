# Sources and Decision Council skill learning

Read when Decision Council reviews workspace code, an IssueTracker ticket or a CodeReview PR, or uses the user's KB.
The main conversation identifies the relevant sources; grounding turns inspected evidence into the
shared factbase. Workers remain independent and do not fetch their own competing versions.

## Select and read the sources

Use the user's current workspace when the question concerns it. If several workspace roots
or IssueTracker sites match, clarify only the ambiguous target. The repository distributing Decision Council is not
automatically the subject. Resolve paths, issue keys and PR links from actual context rather than
requiring the user to list every file. Inspect only sources relevant to the agreed decision.

| Source | What to inspect | What to preserve in the evidence |
| --- | --- | --- |
| Workspace | Local instructions and design documents, relevant implementation, tests/configuration and changes | Workspace root, file/line, actual branch/commit and any uncommitted differences relevant to the claim. Reading a test is not running it. |
| IssueTracker ticket | Summary, description, acceptance criteria where present, status, relevant comments and linked issues | Site plus issue key/URL, field or comment reference and retrieval time. Ticket statements describe intent or reported behavior, not proof that code implements it. |
| CodeReview PR | Description, actual diff and surrounding code, source/target revisions, relevant comments, approvals and build/check results | Host, repository, PR number/URL, inspected revisions and locations. Approvals or green checks do not by themselves prove the requirement is met. |

For a combined request, compare the ticket's intended outcome with the PR diff and relevant workspace
implementation. Do not assume that an open checkout is the PR's current revision. Make any mismatch
explicit before using local files as evidence for that PR. Check relevant pagination and truncation;
unread comments, omitted files or missing build results remain gaps. The review does not post comments,
change a ticket, approve/merge a PR, or edit the subject.

Use read tools already available and authorized in the current execution environment, such as workspace
tools, a configured MCP integration or an approved authenticated CLI. Inspect their actual capabilities;
do not invent connector names or assume that IssueTracker access also grants CodeReview access. A URL alone does
not establish access. Do not search other skills for credentials or copy tokens into prompts/reports.

If the required integration is unavailable, say which source cannot be read. Use a supplied export or
pasted excerpt when appropriate and attribute it as supplied material, with its date and limitations.
If missing evidence prevents the decision, say so; do not replace inaccessible private code with public
documentation or treat a failed fetch as an empty result.

When only the main conversation can access a connector, fetch the authorized source there before
initializing the run. Save the relevant excerpts with their original URLs, revisions, retrieval dates
and gaps in a private source packet; include its path in `primary_sources` so grounding can read it.
Keep `source_targets` pointed at the actual workspace/ticket/PR. The packet is a transport for attributed
evidence, not a claim that grounding itself fetched those sources. If neither context can access the
source, record it as unavailable.

## Record coverage, including failures

Add identified targets to the request. The user does not write this data:

```json
"source_targets": [
  {"kind": "workspace", "ref": "/actual/workspace/root"},
  {"kind": "jira", "ref": "https://actual-site/browse/ACTUAL-KEY"},
  {"kind": "bitbucket_pr", "ref": "https://actual-host/path/to/pr"}
]
```

These are placeholders, not sources to fetch. The optional machine-readable kinds `jira` and `bitbucket_pr` are retained legacy identifiers for compatibility; no data-format migration or connector is introduced. Generic IssueTracker/CodeReview labels do not imply support for arbitrary service APIs. Supported kinds are `workspace`, `jira`, `bitbucket_pr`,
`document` and `web`. Omit irrelevant kinds. For a question based only on the user's description, an
empty target list is valid. Every listed target must appear exactly once in grounding's response:

```json
"source_coverage": [
  {
    "kind": "jira",
    "ref": "exact reference from source_targets",
    "status": "partial",
    "as_of": "actual retrieval date/time",
    "detail": "Description and acceptance criteria read. Comments unavailable; later discussion may change scope."
  }
]
```

Status is `read`, `partial` or `unavailable`. `read` means the material needed for this scoped review
was inspected, not that an entire system was audited. Put revisions, actual tool failures and the
effect of omissions in `detail`. Fact references still identify the original file/line, ticket field,
comment or PR diff location. The coordinator checks coverage structure and carries it through the
human checkpoint, all downstream prompts and report; it cannot prove the claimed access occurred.
Completion describes the agent workflow. Partial evidence must still limit the verdict.

## Reuse improvements to Decision Council's method

The KB exists only to improve the skill's working method. It is not a project knowledge base or
result archive. Case facts, findings, verdicts, IssueTracker/PR details and domain knowledge belong in run
reports and supporting files, even when the user confirms them.

Read the private root from the configured location and inspect its `council_kb.md` before framing.
Select relevant process improvements: clearer scope questions, better source checks, agent handoffs,
model-selection procedure or clearer explanations. Keep their context and limits. Ignore legacy case
content if present; preserve the user's file. A missing KB on first use is normal.

The main conversation applies relevant guidance to framing and model selection, then includes a
small selection for the agents in `skill_lessons`:

```json
"skill_lessons": [
  {
    "purpose": "skill_improvement",
    "lesson": "Decision Council should label PR descriptions separately from inspected code in the fact review.",
    "context": "Reviews combining intent and implementation",
    "limits": "Evidence presentation only; does not determine the verdict.",
    "source": "personal KB path and entry ID"
  }
]
```

Each agent receives these as method guidance, separately from the case evidence. Apply only guidance
relevant to that role. It cannot override the workflow, agreed scope or chosen models. Never cite the
KB as proof about a case or promote it into the factbase. Current source material establishes facts.
For model lessons, retain a selection principle rather than treating an old model name as available.

## Save a confirmed lesson

After delivering a completed or failed review, offer one optional reflection on **how Decision Council worked**.
Save only a method improvement the user supplies or explicitly confirms. For example:

- Save: "Decision Council should check whether the local checkout matches the PR revision before reviewing."
- Keep in the report: "PR 17 does not meet the ticket's freshness requirement."

Write the entry JSON in the private run folder and invoke the coordinator:

```text
python3 <skill>/scripts/council_run.py learn --run <run> --entry <lesson.json>
```

```json
{
  "purpose": "skill_improvement",
  "confirmed": true,
  "lesson": "The confirmed improvement to Decision Council's working method",
  "context": "Which part of the process this applies to",
  "limits": "Where this process guidance does not apply",
  "confirmation": "The actual user reply supplying or confirming this method improvement"
}
```

The helper requires the skill-improvement purpose and rejects additional fields such as results or
verdicts. It cannot judge the meaning of arbitrary prose or authenticate a recorded reply: the main
conversation must check that the entry improves the method and record the real reply. Do not save
case knowledge under a method label.

The KB receives the improvement, context, limits, date, entry ID and originating run ID. The actual
reply is retained in `runs/<id>/learning/<entry-id>.json`; it is not copied into the KB because it may
mention results. Existing KB content is preserved, concurrent writes are serialized and identical
lesson/context/limits entries are skipped. The packaged KB and run report are not modified. Return
the saved KB path, or say the entry was already present. Later runs reuse the process improvement
without importing this case's outcome.

## Integration references

These describe available mechanisms, not proof that a user's account has them configured:

- [Optional legacy Jira API: issues and fields](https://developer.atlassian.com/cloud/jira/platform/rest/v3/api-group-issues/)
- [Optional legacy Bitbucket API: pull requests, diffs, comments and checks](https://developer.atlassian.com/cloud/bitbucket/rest/api-group-pullrequests/)

Use the actual host's integration for Data Center or other deployments; do not send credentials to a
Cloud endpoint just because a reference above describes it.
