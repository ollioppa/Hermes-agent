# Portable reference

Paths in backticks are relative to the package root unless explicitly described as output examples. Read only modules whose triggers apply. Provenance and excluded private inputs: `PROVENANCE.md` and `docs/research/conditional-inputs.md`.

## Preserve the layer model

Keep these layers distinct and execute them in order:

1. **Candidate generation / screening** — finds companies or interesting price regions cheaply and at scale.
2. **Comparative first-pass review** — reviews the whole coarse selection once, side by side, and separates `DEEP_DIVE`, `HOLD_FOR_MORE_DATA`, and `DROP` without changing investment statuses.
3. **Deep dive** — tests business quality, structural damage, competition, financing/capital needs, demand, and the economic mechanism.
4. **Valuation / decision** — asks what future is already priced and assigns BUY, WATCH, or REJECT.

Never infer that failure of one screen disproves the full stockpicking process. State precisely which layer was tested. Trendnormalization is a possible candidate/timing input, not a synonym for the stockpicking strategy.

### Direct-entry routing and frozen deep dives

Keep the stockpicker usable without waiting for the scanner:

- A general direct request such as `Stockpicker: X` bypasses scanner and candidate inbox, runs the lean first pass, and continues automatically into the canonical deep dive when the motor survives; do not insert another user approval between those layers.
- Treat an informal bounded list such as “schau dir X, Y und Z an” as a comparative direct-entry request: complete one side-by-side first pass over the entire named set before ranking or deepening survivors. Do not persist names, create candidate rows, or mutate Radar merely because they were mentioned. An explicit stage-only instruction overrides automatic continuation: finish and verify that stage for every name, then stop; a later request for the most interesting cases authorizes a grounded ranking, not execution of deep dives.
- An explicit `Deep Dive: X` request bypasses first pass and starts the canonical deep dive immediately.
- An already-owned company goes directly to position review or the canonical deep dive, not through candidate routing.
- Do not require a trend signal, candidate row, or screening episode for any direct route, and do not retroactively manufacture one afterward.

When the owner has spent substantial effort stabilizing a deep-dive mandate, freeze it by exact path/version and checksum before changing runtime orchestration. Make the scheduled or interactive wrapper reference that mandate; never paraphrase its economic questions into a second prompt, because duplicate authorities drift and silently discard the accepted method.

### Status vocabulary discipline

Keep research dispositions and product states separate in both prose and durable records:

- `DEEP_DIVE`, `HOLD_FOR_MORE_DATA`, and `DROP` are comparative-research dispositions; they do not place an instrument in the Opportunity Radar.
- `INBOX`, `WATCH`, `READY`, `INVALIDATED`, and `ARCHIVED` are Opportunity Radar states; use them only for cases actually admitted to that product and only under its contract.
- A direct out-of-band deep dive may end HOLD_FOR_MORE_DATA without a comparative first pass. Keep cutoff, thesis, counterpath, falsifier and revisit in its existing complete report path; make that report discoverable without creating a synthetic Candidate or a second research ledger.
- Never answer a status question with a bare label when two status systems are in play. Name the system first, then give exactly one label within it.
- When a completed deep dive is positive and no decisive evidence gap remains, output a **decision-ready proposal to the owner** rather than recycling `DEEP_DIVE`, forcing `HOLD_FOR_MORE_DATA`, or inventing a WATCH condition. This is an output state, not a durable Radar status; wait for explicit authority before mutation. After the owner confirms, admit it directly to `READY` only when the operative product contract supports direct admission and the complete review, sources, snapshots, capacity check, and monitoring rule are present; otherwise stop on the real contract mismatch rather than fabricating a WATCH condition.
- Keep a **research revisit trigger** separate from a **WATCH promotion condition**. A near product, customer, margin, or filing observation may justify reopening the deep dive without making the security one condition away from WATCH. Populate `missing_to_ready` only when the whole economic case is already positive and exactly one admission condition remains.
- A missing quote, source timestamp, or other recoverable metadata is not by itself `HOLD_FOR_MORE_DATA`. It qualifies only when it can decide the economic judgment and no separate structural dependency remains. An unrecoverable historical datum is an evidence limitation, not a future revisit trigger; use a defensible valuation range or leave the episode negative/unresolved for its actual economic reasons.

### Bounded-list intake and interrupted research

1. For a screenshot or video-derived company list, read the actual image with `vision_analyze` before routing research. Preserve the displayed names in the input manifest, then verify issuer, ticker and share class separately; spoken transcripts can omit rows or abbreviate issuers.
2. Check unique input count and exact input/output name-set equality programmatically, not merely equal totals. Keep screenshot observation dates and third-party attribution separate from the current research cutoff; an undated daily decline is neither a current quote nor independent proof of the attributed basket.
3. Bind the same initial scope for every company before delegation: verified instrument and cutoff, operating motor, strongest structural counterevidence, balance/cash-flow condition, defensible rough valuation with quote and denominator, corporate-action/shock distortion, next question and reasoned disposition. For large sets, partition into bounded disjoint groups with this identical contract and a shared source/context cutoff; reserve time for synthesis and save source bodies plus each structured result incrementally. Keep procedural completion separate from research disposition, because a filled row or `HOLD_FOR_MORE_DATA` label does not prove the work was performed.
4. If a research worker times out, inspect saved results and its last actual operations before restarting acquisition. Report the demonstrated stopping point rather than naming a blocked company or network call without evidence. Resume unfinished checks from saved sources; do not replace a requested complete first pass with a provisional shortlist. For full multi-company deep dives, assign one company per bounded worker and perform the pair comparison in the parent after both individual reports are complete; two full investigations plus synthesis can exhaust one worker's budget before either handoff is delivered. On resume, enumerate the missing report, handoff, calculations and verification artifacts explicitly, keep shared source/history/calculation files read-only, and give concurrent finishers symbol-specific output paths so one completion cannot overwrite another's evidence. Acquire only missing evidence and verify the entire batch before advancing: exact unique name-set, identical required scope, substantive completion of every row, consistent price/denominator semantics and current canonical domain context. A timeout proves neither absence nor completion of saved research.
5. State separately which companies have records, which records were substantively checked, and whether any canonical deep dives were completed. Attach a consolidated stage result with sources and limitations; do not describe first-pass routing as a completed investment review or execution by a named productive scanner/stockpicker service unless that service actually ran. An explicitly requested complete initial scan ends with the full-set stage result or a concrete remaining blocker, not follow-on thesis work.

### Screening-to-review procedure

1. Show the complete bounded screening selection first, including the observation date, signal date, and distance from the screening threshold. "Show the selection" means display it; it never authorizes promotion.
2. Keep every fresh screening result in candidate state while reviewing the full coarse set. A price signal alone cannot justify `WATCH`, `READY`, or a purchase.
3. Run one lean comparative pass over every candidate using current primary filings or investor releases. For each candidate capture only: operative motor, strongest counterevidence, balance/cash-flow condition, rough valuation context, corporate-action/Black-Swan distortion, and the next question.
4. Assign research dispositions separately from relative work priority: `DEEP_DIVE`, `HOLD_FOR_MORE_DATA`, or `DROP`. Use `DROP` only for an absolute economic rejection of the current case, never merely because another company is more interesting; otherwise ranking masquerades as evidence of damage. Explain that `DEEP_DIVE` means the motor warrants investigation, not that a future risk is disproved or the stock is attractive. Do not manufacture a numerical score.
5. Synthesize reviewer outputs before presenting them: verify the candidate count, spot-check current primary sources, resolve contradictory verdicts, and re-run any method-specific Black-Swan or pre-shock baseline that could invalidate the screen. Worker consensus is evidence, not the final shortlist. For parallel company workers, independently recalculate the few quantities that carry the ranking, normalize reference-price timestamps, and strip any invented portfolio percentage: a worker may establish company economics, but portfolio size requires the current owned-position inventory and off-ledger exposures.
6. In an interactive one-off review, present the comparative result before opening a full case. In an authorized recurring workflow, continue automatically from first pass into the deep dive only for surviving candidates and surface the result when a final disposition is needed; do not require the owner to trigger each analytical layer.
7. Admission uses the complete canonical mandate once: full individual review, point-in-time sources, bound snapshots/shadow, capacity and the owner’s explicit choice. WATCH needs exactly one last economic condition; direct READY has none. Independent forecast risks must remain visible, not be hidden behind a single WATCH trigger. No separate inflection policy lives in this reference. Research automation never admits WATCH/READY or fabricates conditions.
8. When a clean E2E proof is requested before a real status decision, exercise promotion in an isolated copy of the product state and report the proven boundary. Do not mutate live statuses unless the user separately authorizes the candidate choice.

