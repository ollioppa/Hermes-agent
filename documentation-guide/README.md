# Documentation Guide

**Start here: [worked example](example.md), then [Quickstart](#quickstart).**

For method details: [open the walkthrough](https://ollioppa.github.io/Hermes-agent/documentation-guide/walkthrough.html). Its [source manifest](walkthrough.json) is for inspection, not required reading.

Created by Roland Chotika with AI assistance.

[Quickstart](#quickstart) · [Presentation](#presentation) · [Offline visual entry](START-HERE.html)

## Quickstart

- **What:** reusable instructions for writing or revising guides from sources.
- **Why:** keep agreed meaning and its place in the reader's path through later edits—not merely the same keywords.
- **Fit:** maintained guides, start pages and how-tos. A normal prompt is enough for a sentence correction.
- **Need:** an AI tool that accepts pasted text or attachments, source material you may share, and a place to save the answer. No special assistant or installation.

```text
Sources + reader's goal
          ↓
Shared facts and decisions
      ↙             ↘
Quickstart      Presentation
 act now       understand why
      ↘             ↙
 Revisions preserve meaning
```

**Start:** attach or paste [METHOD.md](METHOD.md) and [example.md](example.md) into a new chat, then send:

> Apply METHOD.md to the Source facts, assignment and Before text in example.md. Produce a clearer English how-to and a concise decision-preservation check. Use only those facts; ignore the provided After and review until you have drafted your answer. Do not publish or modify files. Distinguish checks you actually performed from checks still needed.

**Expect:** a how-to with prerequisites, exact action, expected result and recovery, plus a check against the source facts. Compare your answer with the labelled example; identical wording is not required. This is a runnable chat assignment, not a special slash command. Do not paste private material into a service unless its use is authorized.

If attachments are unavailable, open the files in a text editor and paste their contents with filename labels. If the assistant cannot execute commands, it must label the command check unperformed; you can run the example locally or leave it open. If it cannot read the input, stop the affected rewrite and supply the missing text rather than asking it to infer facts.

For your own document, provide METHOD.md, your sources, the current draft if any and prior decisions. State the reader, task, output language and destination. Ask for two paths only when both first understanding and repeat use are needed. Save agreed decisions alongside the maintained document, not just in a disposable chat.

## Presentation

Readable sentences can still lose what a reader needs. Shortening a guide may remove its reason to exist, move a prerequisite after the action, or hide an essential answer in an optional explanation. Documentation Guide connects writing to source material and keeps those decisions available for the next revision.

Its specific contribution is a reusable editorial discipline: establish the subject and supported value first, select appropriate reader paths, then check that changes preserve meaning, importance and location. A capable assistant can do the same from a detailed prompt. This package organizes those instructions; it does not add model capabilities or establish measured savings.

The diagram above shows why Quickstart and Presentation share facts. The first serves immediate action, the second explains why and how. They are not duplicate manuals, and a focused how-to can use one path. [METHOD.md](METHOD.md) is the operational instruction; [REFERENCE.md](REFERENCE.md) explains the decisions behind it.

The [new illustrative example](example.md) shows the method applied to an offline line-counting how-to: source facts, a deliberately weak draft, a revised version and a preservation check are all inspectable. It is not a recovered historical case or an independent user experiment.

Start with the [Quickstart](#quickstart), then judge the actual answer: can a reader see the task, take the first action and recognize success without guessing? Automated checks and the author's own review do not establish that a new reader has understood it. Check the resulting guide in its actual destination and, when required, observe the intended reader completing the task.

## Scope and package status

The files are offline-readable; using an online AI service is separate. Browser layout is provided by START-HERE.html, not guaranteed for every Markdown renderer. Wiki publishing, automatic skill discovery and recipient-side AI execution are not bundled integrations.

This sanitized export is **published as part of the project collection**. Rights and redistribution remain subject to [PROVENANCE.md](PROVENANCE.md); MIT has been explicitly authorized for this export; see [LICENSE](LICENSE). The package contains README.md, METHOD.md, REFERENCE.md, START-HERE.html, example.md, PROVENANCE.md, LICENSE, walkthrough.html and walkthrough.json. Internal review records are not included. Do not infer an open-source license from another component of a combined package.
