# Private storage

Read at first use or a storage failure; reuse the resolved paths later in the chat.
The helper uses Python 3.10+ and its standard library. Use the available `python3`, `python`
or `py -3`; substitute its executable and the installed skill path below.

```text
<python> <skill>/scripts/storage.py status
```

`needs_location`: ask “Where should I keep your personal Discovery reports and
knowledge base? Choose a private folder; I will remember it locally.” Wait before
discovery questions. Then configure that absolute path:

```text
<python> <skill>/scripts/storage.py configure --root <chosen-folder>
```

The helper creates `reports/` and a missing `discovery_kb.md`, preserving existing
notes. Its pointer is `~/.config/discovery-agent/location.json` on macOS/Linux or
`%APPDATA%/discovery-agent/location.json` on Windows, containing only `{"root":"..."}`.
An existing pointer remains compatible. Use `--replace` only for an explicit change
of personal location. An unavailable root needs the user's new choice, not a guessed
fallback. If the pointer cannot be saved, retain the chosen path for this run and
explain that the next session will ask again.

Keep private files outside the shared skill, preferably outside repositories. A
user-chosen location inside Git must already be ignored and untracked; the helper
checks this and rejects redirected subfolders. Do not edit shared ignore rules.

## Save a report

Write the report text to a private temporary Markdown file, then:

```text
<python> <skill>/scripts/storage.py save --source <draft.md> --name DISCOVERY_<short-title>.md
```

For an explicitly supplied one-run destination, replace `--name` with
`--output <absolute-report-path>`; it leaves the KB root unchanged. Existing files
are refused. Choose another name or use `--overwrite` only when explicitly requested.
Return the saved path. On failure, keep the draft and ask for an accessible path;
do not claim success. The helper checks storage, not truth, clarification or readiness.

If Python or pointer persistence is unavailable, use the host's file tools for the same layout, pointer,
privacy and overwrite rules. This is a supported fallback, not a required installation.
Verify the actual write; never put private data in the skill as a workaround.

## Personal learning

Before clarification, select relevant entries from the user's KB; do not load every
old case. After saving, offer one optional reflection: “What did we almost miss, or
which question would help next time?” Append only a user-supplied or confirmed reusable
lesson, under a dated heading, with **Situation**, **Lesson / next question**, **Basis**
and **Limits**. Mark tentative patterns, omit secrets and unnecessary case text, and
preserve existing entries. A skipped reflection adds nothing. Never update the shared
seed guide or another user's KB during a normal run.
