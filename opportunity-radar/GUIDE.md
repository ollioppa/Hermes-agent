# Opportunity Radar — user guide

Keep researched ideas, admitted opportunities and actual holdings separate. Opportunity Radar combines agent-led equity/ETF research with a deterministic SQLite record of decisions, snapshots and reviews. Its contribution is the controlled handoff from research to human admission and confirmed position changes—not automatic stock selection or trade execution.

```text
Scanner or direct idea → agent research → proposal → human admission → WATCH / READY
Confirmed holding → monthly review → recommendation → confirmed execution record
```

**Start here:** exercise the synthetic workflow below. Then read [AGENTS.md](AGENTS.md) for a real research assignment, or open [the technical walkthrough](walkthrough.html). [README.md](README.md) remains the canonical setup and export-boundary reference.

## Is this a fit?

Use it if you want a bounded research inbox, explicit readiness conditions and traceable review/position history. A personal watchlist is simpler if you do not need those distinctions. READY means decision-ready, not bought. A recommendation to EXIT does not alter holdings. No return advantage or investment quality is established by passing software tests.

An intelligent agent with an LLM and authorized research tools is required for the research product. Hermes is not mandatory; compatibility with an arbitrary harness is not proven. Python alone runs the deterministic core, not a substitute Deep Dive.

## First safe workflow

From `opportunity-radar/` in a public checkout, use Python >=3.11. Install dependencies from `pyproject.toml` in your own environment; scanner/demo dependencies include DuckDB, Hugging Face Hub and yfinance. Installation may access package servers; the synthetic demonstration does not fetch market data. POSIX locking is needed by the mailer scripts.

```sh
python3 -m venv .venv
.venv/bin/python -m pip install . pytest
.venv/bin/python -B scripts/offline_demo.py --output demo-output
```

Choose a **new** output directory. The demonstration refuses an existing destination instead of reusing a potentially real database. It writes a synthetic SQLite database, invented inputs/research, `reader.md`, `local-mail.md` and `summary.json` there. `local-mail.md` is a local file, not a sent message.

**Expected from source assertions, not a new execution in this documentation task:** one screening signal; repeated publication returns `ALREADY_PUBLISHED`; a separate admission produces READY; an EXIT recommendation leaves the holding unchanged; a confirmed synthetic TRIM leaves eight units. Inspect `summary.json` for `synthetic: true`, `live_network: false`, `live_mail: false` and `llm: false`. These labels describe the example, not a runtime firewall.

For a smaller core smoke without scanner dependencies, the existing alternative is `python3 -B scripts/smoke.py`. Neither entrypoint proves an authorized research or delivery integration.

## Failure and recovery

- **Existing output directory:** keep it for inspection and use a different new destination. Do not point the demo at a real DB or delete unknown state to force a retry.
- **Missing imports:** use the environment where this package and its dependencies were installed. Do not depend on a private sibling checkout.
- **ContractError in real input:** inspect the named review, snapshot, episode or capacity constraint. Correct the evidence/payload; bypassing validation changes the product guarantee. `--confirmed-by owner` is an audit label, not authentication.
- **Unresolved mail attempt:** reconcile the actual delivery identity and Sent evidence before retrying. The implementation intentionally refuses ambiguous resend. Do not clear pending state to force SMTP.

## Moving beyond the demonstration

Read the product and task-specific contracts, `docs/runtime-dependencies.md`, then the relevant prompt via AGENTS. The local research references are included; conditional operator inputs remain operator-owned. Direct ideas do not require inventing a scanner episode. Candidate research can propose a disposition but cannot authorize admission. Confirmed holdings can exist without a prior radar case.

The quarterly product covers WATCH/READY and pending proposals; monthly review covers linked active positions. Watchdog coverage needs an explicitly configured rule. Review and watchdog outputs do not themselves mutate status or holdings.

Live price commands and scanner `main` can access providers. **`--no-publish` is not offline.** No scheduler, account or mail service is installed. Live mail additionally requires explicit enablement, sender, an external Markdown-to-mail helper and configured transport; that integration is not portable out of the box and was not exercised here. Keep own DB/output locations explicit before any authorized live work.

## Follow the decisive handoff

- `scripts/offline_demo.py:84–110`: review leaves quantity unchanged, confirmed event changes it, local transport captures mail.
- `src/opportunity_radar/db.py:RadarDB.record_position_review`: validates the active episode and baseline, inserts a review without changing holdings.
- `src/opportunity_radar/db.py:RadarDB.confirm_position_event`: requires the audit actor, checks execution identity/date, then changes holdings transactionally.
- `scripts/run_trend_screening.py:compute_current_signals` and `publish`: numerical eligibility is separate from transactional inbox publication and suppression.
- `src/opportunity_radar/mailer.py:deliver_mail_once`: delivery key, recipient, subject and body hash bind receipts and retry handling.

Source boundary: monorepo commit `ddac35ef8362d1f93356142ca7f651888f2146e5`; source inspection only. The README's prior test counts remain historical claims, not new results. Known limits include same-year stale prices, price-return rather than complete total-return/FX evaluation, pending reconciliation/crash durability, incomplete legacy enforcement of `investment_frame`, and no dedicated resumption command for personally deferred WATCH without an open condition.
