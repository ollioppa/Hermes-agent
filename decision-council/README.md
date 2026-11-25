# Decision Council

Created by Roland Chotika with AI assistance.

Stress-test an uncertain design, plan or root-cause thesis. The method combines a shared evidence base with independent challenges and a saved verdict; it informs a decision without approving or executing changes.

**Grounding → human fact review → four blind workers → outflanker → chair**

## Start

1. Make [SKILL.md](SKILL.md) and its references available to the main agent. No installation destination, UI command or automatic registration is assumed.
2. Ask: “Use Decision Council to review this plan: <file>. What could fail, and what evidence would change the decision?”
3. Agree scope, thesis/antithesis and explicit available models. Choose a private folder outside Git repositories and this package. Review the gathered facts before the four workers begin.
4. Expect a plain-language verdict and saved report with findings, sources, limitations and model records. A complete workflow may conclude that the question is undecidable; an incomplete workflow is not a completed verdict.

[Read the visual guide](START-HERE.html) or [explore the fictional interactive examples](demo.html). Both are offline documents; the demo invokes no models and writes no reports. An ordinary conversation is sufficient for a simple lookup.

## Required capabilities and execution boundary

Python 3.10+ and its standard library run the existing local file coordinator. The agent environment must support authorized file/tool execution, seven genuinely independent role contexts, isolation of the four workers from one another and the main chat, and actual binding to the explicit models the user chooses from verified availability. One model in all seven separate contexts is valid. Model capability is not limited by this package; availability, isolation and binding must be checked on the target environment.

The coordinator calls no model or network API. The main agent dispatches actual roles and submits raw responses with truthful execution metadata. See [execution binding](references/execution-binding.md), [model selection](references/model-selection.md) and [sources and learning](references/sources-and-knowledge.md).

The existing `tool-model` route requires per-call model selection. The optional `custom-agent` route emits `.agent.md` definitions and works only where that exact format, discovery, model fields and restrictions are supported. It is not a universal adapter. No new runner, adapter or replacement workflow is included.

```text
python3 <package>/scripts/council_run.py --help
python3 -m unittest discover -s <package>/tests -p 'test_*.py' -v
```

Tests use synthetic responses, not real models. Use isolated HOME/config and a private temporary directory outside **every** `.git` ancestor. The storage check walks all filesystem ancestors: adding a nested Git repository does not create an acceptable private-storage boundary. Do not disable or patch the guard. Local tests cannot prove live model binding, source access or authentic human approval; those still require a real authorized run on the target environment.

## Explicit package allowlist

Runtime instructions: `SKILL.md`, `kb/council_kb.md`, `references/execution-binding.md`, `references/model-selection.md`, `references/sources-and-knowledge.md`.

Runtime coordinator: `scripts/council_run.py`.

Supporting material: `LICENSE`, `README.md`, `START-HERE.html`, `demo.html`, `tests/test_council_run.py`.

Private original design/history and maintenance plans are deliberately excluded. Generic seed guidance and fictional examples remain. No personal runs, case facts, credentials or user KB are included. Existing `council_run.py`, `council/location.json`, `council_kb.md`, JSON fields, commands and generated state formats remain compatible technical identifiers.

## Origin and rights

Privately developed tools, voluntarily adapted for a separate use context; this export is not evidence of an employer assignment, endorsement or ownership. This sanitized export is licensed under the [MIT License](LICENSE), explicitly authorized by Roland Chotika. Copyright (c) 2026 Roland Chotika. Third-party rights and required notices remain unaffected; dependencies and external data retain their own terms. Private operating data, credentials and unrelated original history are excluded.
