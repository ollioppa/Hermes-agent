> Export-Vertragsreferenz, kein Nachweis aktiver Jobs oder produktiver Zustellung. Persönliche Betriebsbindungen wurden entfernt.

# Screening Contract

> **Status note:** The four-disposition contract below is productive. Schema, CLI, scanner suppression, tracked prompt, and the scheduled research worker use the same contract.

Opportunity Radar screening is a price-based candidate lane, not an investment decision engine.

## Authority

Automation may write a completed screening cycle, deterministic hits and at most ten unfinished active research rows (including budget pauses and RESEARCH_INCOMPLETE, excluding completed AWAITING_USER). It must never create or change `WATCH`, `READY`, `ARCHIVED`, `INVALIDATED`, reviews, watch conditions, case snapshots, transitions or orders. Manual `promote-candidate` uses the same transactional admission owner as direct case import. An explicit candidate ID binds identity and episode; WATCH or direct READY admission links and closes that candidate atomically. Direct entry without a candidate remains supported. No synthetic WATCH condition is required for READY.

Candidate research dispositions are separate from investment statuses and are never case transitions:

- `DEFER_EPISODE`: the current economic/price case is not attractive. Archive the research episode, preserving decisions. A specific date or event/price revisit is allowed: dates become due, event/price triggers require explicit Owner activation through `next-candidate --candidate-id ID --confirmed-by owner`. No automatic price interpretation or Radar admission.
- `RESEARCH_INCOMPLETE`: exactly one decision-relevant, currently unavailable fact prevents judgment. Keep the candidate `OPEN`, but suppress automated reruns until a recorded `revisit_after` date or an explicit `revisit_trigger`. Automation must not invent or satisfy that trigger.
- `SCREEN_DISTORTED`: a split, rights issue, acquisition, pandemic/shock baseline, or comparable corporate-action distortion prevents economic interpretation of the trend signal. Archive that signal episode only; this is not a judgment that the company is poor.
- `AWAITING_USER`: the economic dispute, valuation, counterevidence, and falsifier are decision-ready. Keep the candidate `OPEN` for Owner's manual decision.

`EXCLUDE` is human-only and permanently suppresses the stable identity in later screens.
An archived Radar case is not EXCLUDE. A later completed signal month may produce a new candidate only if its calendar month-end is after the documented archive date and it is later than any known candidate episode previously admitted to that case. Missing archive provenance remains blocked. Non-archived cases still suppress duplicates. Screening and manual candidate admission share this existing DB-owned suppression check; an old OPEN candidate cannot bypass the archive boundary.

Confirmed re-admission creates a new case_id with its own review and shadow, never reactivates or overwrites the archived case. Historical identity aliases retain each case binding; only one non-archived case per symbol may exist. Direct explicit import without a candidate is still supported. Existing position links and historical evaluation records stay attached to their original case IDs. No automated disposition may create or change `WATCH`, `READY`, `INVALIDATED`, or a case review, condition, snapshot, transition, order, or position.

The scheduled worker processes one due new or resumed investigation. The existing Candidate owner may transactionally reopen a due research deferral; it never reactivates an archived Radar case. `next-candidate` returns previous decisions and read report bodies. `candidate-work` appends a resumable report/source cutoff/next-work record in existing metrics_json, not a new disposition. An acquisition budget cannot become an economic rejection. Its decision command binds `--candidate-id` to the exact selected row and `--signal-date` to its `first_entry_month`; a symbol alone is not a global security identity. An identical retry returns the original decision ID even after episode deferral; it must not apply the old result to a later episode. `AWAITING_USER` requires a nonempty existing report and reader summary; file presence is not proof of substantive economic completeness. Historical decisions are not silently relabelled. It performs the comparative first pass and, only when warranted, the deeper company review in the same autonomous task. It stores the disposition, reason, and any required revisit boundary without mutating Radar or position state. A candidate that remains `RESEARCH_INCOMPLETE` is not eligible again before its `revisit_after`; an explicit trigger is visible for human action but is never guessed by automation. Viable cases are stored with a reader-led explanation and appear only in the quarterly WATCH letter while their decision remains bound to the current signal episode. Permanent exclusion remains a human decision.

## Trend-normalisation lanes

The US lane screens the current SPY/Nasdaq-100 stock union with adjusted daily prices from `AmirTrader/YahooFinance` on Hugging Face. The hosted snapshot is sourced upstream from Yahoo Finance through `yfinance`; its repository license does not override upstream market-data rights. Use is local personal research, not redistribution.

The Europe lane screens the current STOXX Europe 600 holdings, and the ETF lane screens the curated ETF list. Their adjusted histories are maintained locally with `yfinance`. The same Yahoo upstream-rights caveat applies. Newly listed instruments without five December anchors are reported as covered but not trend-eligible.

The historical Drive corpus ends on 2024-12-31. For every symbol with December-2024 overlap, the runtime rebases the old series by the median `HF adjusted_close / Drive adjusted_close` ratio. A symbol is not stitched if the overlap has fewer than ten observations or a ratio span above 0.001. Symbols without overlap use only their available HF history.

The deterministic method is:

- five December adjusted closes before the run year;
- linear OLS in absolute prices with positive slope and positive endpoint;
- first closed month in the run year at or above 130% of the projected trend;
- first strictly later closed month at or below 110% of the projected trend;
- a current candidate must first return in the current year and remain at or below 110% using the latest available daily adjusted close.

Each hit stores the source, five anchors, slope, run month, first return month, current price date, price, projected trend and ratio. Black-Swan/pre-shock and Consumer-Covid overrides remain explicitly marked for human review; automation does not silently guess them.

## Runtime

`scripts/run_trend_screening.py --refresh` refreshes all three universes, performs the US stitch and common calculation, writes inspectable JSON/CSV output under `output/screening/<date>/`, and atomically publishes hits and bounded candidates to SQLite. A cycle is bound to the as-of date and a digest of the actual US/global monthly and latest calculation inputs. Hugging-Face revision is pinned before refresh and recorded separately; no-refresh leaves remote provenance unknown. Repeating the same input state is idempotent.

The local radar reader shows selected candidates and reserve count. The quarterly WATCH letter includes only completed decisions bound to the current signal episode; raw screening hits and reserve inventory remain outside the mail. Stocks and ETFs retain their own identity and kind; the ten-unfinished-research cap applies across all lanes; completed AWAITING_USER remains visible outside that work limit.
