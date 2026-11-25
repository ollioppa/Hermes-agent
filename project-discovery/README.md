# Project Discovery

Created by Roland Chotika with AI assistance.

Clarify an uncertain question, task or spike before committing to work. Adaptive questions turn supplied evidence and user answers into a saved answer or actionable handoff—not an unsolicited implementation project.

**Sources → material question → user answer → saved answer/handoff**

## Start

1. Make [SKILL.md](SKILL.md) and its relative references available to your agent. No particular installation path or UI command is assumed.
2. Ask: “Use Project Discovery to clarify this question: …”. The agent reads relevant supplied evidence and asks only questions whose answers could change the result.
3. On first use, choose private storage. At completion, expect an actual saved report, its path and a brief answer. Task readiness is not permission to execute.

Use an ordinary direct answer when the request is already clear. This method adds adaptive clarification, explicit evidence boundaries, a reusable handoff and optional user-confirmed learning—not a requirement for seven agents.

## Required capabilities

The main agent needs dialogue, access to authorized sources and verified file writes. Optional independent read-only delegation helps with extensive inputs; direct reading remains supported. The storage helper uses Python 3.10+ and the standard library. [Storage](references/storage.md) documents an equivalent file-tool fallback when Python or pointer persistence is unavailable. Git is needed only to validate a chosen storage location within a repository; it must already be ignored and untracked.

```text
python3 <package>/scripts/storage.py --help
python3 <package>/scripts/storage.py status
python3 -m unittest discover -s <package>/tests -p 'test_*.py' -v
```

Tests write temporary fixtures. Run with a private isolated HOME/config and temporary directory, not with production state. Do not weaken storage checks to accommodate a test environment.

## Explicit package allowlist

Runtime instructions: `SKILL.md`, `kb/discovery_kb.md`, `references/question-playbook.md`, `references/report-contract.md`, `references/storage.md`.

Runtime helper: `scripts/storage.py`.

Supporting material: `LICENSE`, `README.md`, `tests/test_storage.py`.

No case reports, private KB, credentials, historical runs or private maintenance plans belong in the package. The shared KB is generic guidance; user learning stays private. Existing `discovery-agent/location.json`, `discovery_kb.md`, `DISCOVERY_…` and CLI arguments are deliberately retained as compatible technical names, not installation claims.

## Origin and rights

Privately developed tools, voluntarily adapted for a separate use context; this export is not evidence of an employer assignment, endorsement or ownership. This sanitized export is licensed under the [MIT License](LICENSE), explicitly authorized by Roland Chotika. Copyright (c) 2026 Roland Chotika. Third-party rights and required notices remain unaffected; dependencies and external data retain their own terms. Private operating data, credentials and unrelated original history are excluded.
