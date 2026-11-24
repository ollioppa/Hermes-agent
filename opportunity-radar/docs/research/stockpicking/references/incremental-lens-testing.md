# Portable reference

Paths in backticks are relative to the package root unless explicitly described as output examples. Read only modules whose triggers apply. Provenance and excluded private inputs: `PROVENANCE.md` and `docs/research/conditional-inputs.md`.

# Testing an Incremental Analytical Lens

Use this protocol when a new conceptual idea may refine an established stock-review process but has not yet earned a product gate, score or separate factor.

## 1. Pre-register the experiment

Before producing reviews, write down:

- the bounded candidate set and why it spans different mechanisms rather than repeated versions of one thesis;
- one common evidence cutoff;
- non-goals, especially no live status change and no claim of alpha from a small feasibility sample;
- the existing review as baseline and the proposed lens as shadow;
- the exact material-difference rule and the continuation/kill gate.

If production state must remain untouched, hash or snapshot it before the experiment and compare it again afterward. A successful research run is not authority to mutate `WATCH`, `READY`, `BUY`, `DROP` or permanent exclusions.

### Calibrating an admission policy rather than a new lens

When the disputed change is a policy threshold — for example requiring observed operational inflection or allowing only one unproved success — do not measure only false-positive protection. Pre-register a balanced matrix with four distinct roles:

1. positive controls the process should admit;
2. negative controls it should reject;
3. seductive losers that challenge a more opportunity-seeking policy;
4. pre-inflection winners that challenge an overly defensive policy.

Use at least two mechanisms in each role, and pair companies around the same economic dispute where possible: platform transition, bottleneck versus incumbent decay, mature franchise renewal, fallen platform valuation, or technology scale-up. This makes the comparison about causal discrimination rather than one-sided case selection.

Keep `research quality` and `portfolio admission policy` as separate outputs. A cleanly analysed turnaround can remain excluded by policy; that does not make the analysis wrong. Conversely, an empty watchlist has perfect false-positive avoidance but proves no selection skill. Preserve the current policy until both directions have been reviewed and the trade-off between false positives and false negatives is explicit.

Reject any historical aggregate as a calibration corpus when names, point-in-time verdicts, publication cutoffs or source packets are missing. Record the provenance gap and build a new auditable sample instead of reverse-engineering attractive examples from the reported hit rate.

For each outcome anchor, use the first executable close after the cutoff release and a same-start split/dividend-adjusted benchmark. Keep two judgments separate: whether the frozen economic mechanism was correct, and whether the security outperformed. Repricing, policy support or a later new episode can make those answers diverge.

## 2. Freeze symmetric evidence

Create one fact-only packet per company from sources available by the cutoff. Include business and cash-flow drivers, latest results and guidance, financing and capital needs, valuation inputs at a dated reference price, market structure, competition and unresolved gaps. Keep recommendations and lens-specific conclusions out of the packet.

Keep packet-boundary metadata neutral. Do not write even exclusion notices such as “outcomes removed” or “winner/loser language excluded” inside the reviewer-facing packet: those terms can prime the reviewer and also create false positives in mechanical leakage scans. Say only that the packet contains information available within the stated evidence boundary. Scan case-insensitively for disposition labels, recommendations, outcome vocabulary and named control roles before hashing the final packet.

Give baseline and shadow reviewers the identical packet. Do not let either reviewer add web research: asymmetric source access can masquerade as analytical value.

Extract and test every URL, but do not equate HTTP success with source validity. Inspect the title, document header or content prefix when filenames, dates or descriptions look inconsistent; redirects and misleading filenames can resolve successfully to the wrong document.

### Re-run an existing deep dive under a new format

When the question is whether a new review format changes an earlier conclusion, isolate the **format effect** from the **information effect**:

1. Freeze the original memo byte-for-byte, including its evidence cutoff, reference price, decision, missing condition and source list.
2. Recover the authoritative portfolio or sector context that was available at that cutoff. Do not silently replace it with today's regime.
3. Derive a verdict-free fact packet from the frozen memo and contemporaneous context. Preserve facts, calculations, limitations and exact URLs; remove the old verdict, ranking, recommendation, missing condition and personal decision frame so the new reviewer is not anchored.
4. Give the new-format reviewer only that packet and the new mandate. Prohibit browsing, later filings, later prices and outcome knowledge.
5. Compare owned economic claim, load-bearing valuation assumption, falsifier hierarchy, missing condition and final status. Classify an unchanged status with a sharper causal model separately from a material thesis or status change.
6. If a current update is also useful, run it **after** the frozen comparison and label it as a separate current-information review. Never mix new evidence into the format test, and never count the live case as another historical control.
7. For a live case with a complex capital stack, require an adversarial arithmetic audit before accepting the prompt's verdict: reconcile basic and diluted shares, cash, debt, preferred market value versus stated/liquidation claim, recurring financing burden, and operating-business value. A mechanically correct gross-asset multiple can still imply the wrong common-equity claim when these layers are mixed.

For domains with a canonical radar or database, bind the contemporaneous state/report/thesis register into the frozen context. The company filing explains the issuer; the radar explains the regime and must not be reconstructed from memory.

## 3. Preserve blindness

Use separate mandates and independent workers:

- **Baseline:** apply only the operative stock-review procedure; do not reveal the shadow questions or output.
- **Shadow:** answer only the proposed lens questions; do not reveal the baseline review or output.

Restrict each worker to its mandate and packet. Have workers return content rather than write into the shared repository; the parent freezes the outputs after all workers finish. Record the exact mandate files and input hashes in the manifest.

Before dispatching the full fan-out, verify every packet at the exact path the workers will receive and compare its hash with the frozen source. Do not trust an aggregate helper message such as “N files written”: inspect each write result or perform a path/readability preflight, because a missing handoff directory can invalidate the entire blind batch without changing the research design.

## 4. Compare only predeclared decision deltas

For each case, classify the shadow result as:

- `MATERIAL_DIFFERENCE` — changes a load-bearing valuation assumption, a concrete observable falsifier, or the hypothetical research disposition;
- `PROCESS_ONLY` — adds a worthwhile question or presentation improvement without changing the decision frame;
- `NO_INCREMENTAL_INFORMATION` — restates competition, moat, capex or valuation already captured by the baseline;
- `INVALID` — cutoff, evidence symmetry or blindness was broken.

Check directionality. A lens that merely produces more bearish language is not automatically useful; require both attack and renewal mechanisms to be treated symmetrically. Do not count the same substitution mechanism separately as moat, capex and valuation defects.

Treat a disposition-only change as **weak materiality** until parent adjudication. If the shadow changes `DEEP_DIVE` to `HOLD_FOR_MORE_DATA` without changing a load-bearing valuation assumption or improving the observable falsifier, reviewer risk tolerance is a sufficient alternative explanation. Report the literal contract label, but do not use such cases alone to justify continuation.

## 5. Decide before integration

Continue to a larger prospective test only when several cases show specific material differences, the differences are not all generic downgrades, extra source access or reviewer variance does not explain them, and reader burden stays small. Otherwise keep the insight inside the normal deep dive and kill the separate component.

The output bundle should contain source packets, both mandate versions, frozen baseline and shadow reviews, per-case comparison, source verification, a manifest of hashes and models, and proof that protected production state did not change.
