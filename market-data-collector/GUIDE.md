# Market Data Collector — user guide

Turn provider observations into consistent BTC/MSTR and market tables, then read a structured snapshot from Google Sheets. The useful contribution is the shared calculation, schema and missing-data handling between collection and consumption—not simply downloading prices.

```text
Providers → dated rows + indicators → Google Sheets → snapshot + mechanical score
Synthetic inputs → same row builders → memory sheet → same snapshot consumer
```

**Start here:** use the offline example below. For implementation details open [the source-bound walkthrough](walkthrough.html); retain [README.md](README.md) as the setup, live-operation and provenance reference.

## Is this a fit?

Use this project when you need the included BTC/MSTR, market/sector and optional macro contracts across repeated collection and reporting. A CSV download is sufficient if you only need a few prices; this project adds provider dependencies, positional sheet schemas and maintenance responsibility. It is not a trading system, research agent or email service. Its score is mechanical, not investment advice.

## First safe workflow

Work from `market-data-collector/` in a public checkout. Use Python with the dependencies in `requirements.txt`; the source uses Python 3.10+ syntax. The README records historical installation checks, not a compatibility guarantee for every interpreter. A fresh dependency installation needs package-network access; installation is distinct from the offline example.

1. Follow the README's virtual-environment setup if dependencies are missing. No original installation or private sibling directory is needed.
2. Run only the synthetic entrypoint:

   ```sh
   python -B -m examples.offline_pipeline
   ```

3. Inspect JSON on stdout. Expected, **from assertions in the source rather than a new run here**: `input_kind` is `SYNTHETIC_ONLY_NOT_MARKET_DATA`, the fixed date is `2026-10-18`, the score is `complete`, and the sector snapshot is `ready` with eleven sector entries. Both tables are built from the fixed synthetic history. Provider-looking provenance fields are synthetic too.

The example patches acquisition and sheet transport in its own process, then calls the actual row builders and snapshot consumer. It disables macro consumption. It does not prove real provider availability, correct credentials, live data quality or full macro readiness.

## If the first run fails

- **Missing module:** activate the intended environment and install the unchanged requirements; do not add private directories to `PYTHONPATH`.
- **Wrong `src` import or assertion failure:** run from this project directory with its own source tree. The example checks loaded project-module locations. Preserve the traceback before changing dependencies or expected values.
- **Need a stronger offline boundary:** the existing `tools/verify_local.py` provides a macOS `sandbox-exec` verification path and writes `.verification/`. See the README before invoking it; it is not cross-platform and was not run for this documentation task.

## Before enabling live operation

A **dry-run is not offline**. Daily refresh reads Sheets for schema checks and fetches providers even when sheet writes are disabled. The CLI defaults to dry-run; internal writer APIs are genuine writers and can have different defaults. Do not use imports or legacy jobs as a substitute for the documented CLI safety boundary.

You must supply your own spreadsheet, service-account credentials and applicable provider credentials/permissions. Review `config.example.env`, headers in `src/config/settings.py`, and the README's explicit `--write` boundary. Full backfill replaces selected tables; daily refresh updates a recent window using longer calculation history and merge protection. A schema mismatch calls for reviewing the intended header—not deleting production data. Daily lock contention exits with code 75; a partial macro/window result exits with code 2. Investigate the reported lane rather than treating partial success as complete.

Macro is optional and not ready out of the box: licensed archive inputs and BDC exports are deliberately absent. Funding is held pending a documented settlement contract. Sector ETFs are price-return proxies, not official total-return indices. Missing history may legitimately yield unavailable indicators.

## Follow the code

- `examples/offline_pipeline.py:53–101`: acquisition substitution, real consumer and success assertions.
- `src/scripts/run_daily.py:66–85`: explicit write flag, locking and exit status.
- `src/services/backfill.py:run_daily`: schema check, computation window, upsert and partial result (the walkthrough embeds its exact source extent).
- `src/services/google_sheets.py:upsert_rows`: date-keyed merge preserves existing cells when new values are empty.
- `src/services/composite_thermometer.py:build_daily_thermometer`: a total score requires all four active components; partial availability does not become a fabricated total.

Source boundary: monorepo commit `ddac35ef8362d1f93356142ca7f651888f2146e5`. Documentation inspection only; no target execution or live verification was performed. Installation history in the README remains attributed historical evidence.
