# Portable reference

Paths in backticks are relative to the package root unless explicitly described as output examples. Read only modules whose triggers apply. Provenance and excluded private inputs: `PROVENANCE.md` and `docs/research/conditional-inputs.md`.

# Recurring financial briefings: deep analysis without reader overload

Use this reference when a Daily or Weekly turns a large evidence corpus into a financial reader product, especially when the report also carries scores, regimes, scenarios, or alerts.

## Reader contract for important finds

A material source is not finished when its numbers have been copied correctly. For each lead finding, establish enough of this chain for the owner to follow it:

1. **Ausgangsniveau:** What is the denominator, portfolio size, prior quarter, historical norm, cap, or comparison universe?
2. **Vergleich:** Versus when or versus what did the value change? Do not mix unlike samples or calculation bases without saying so.
3. **Trend:** Is this a one-off mark, a second consecutive quarter, an acceleration, a moderation, or a migration from unrealized to realized loss?
4. **Mechanik:** Through which balance-sheet, funding, flow, or credit-quality channel does it matter?
5. **Gegenkraft:** What evidence from the same source or period limits the bearish/bullish reading?
6. **Bedeutung:** What changes in the regime, watchpoint, or thesis—and what does not?

Not every item needs six visible subheadings. The writer must know the chain; the reader should receive the shortest prose that preserves it.

## Evidence classes must not be blended

Label internally before synthesis:

- current event;
- newly published information about an older event;
- structural research/mechanism;
- manager narrative;
- current observable market mechanism;
- counterevidence.

A structural paper may explain transmission but cannot prove that transmission is currently worsening. A manager statement is context with incentives, not a hard counterforce. Capital formation in a favored new segment may prove dispersion rather than stability of legacy portfolios.

## Score and prose are different products

A Weekly score must have an explicit owner and update contract. Do not infer score quality from a polished report.

Audit the chain:

```text
weekly evidence → deduplicated events → axis levels → momentum/breadth
→ regime/alert decision → reader explanation → persisted weekly state
```

Required distinctions:

- **Level** is not **momentum**.
- **Regime** is not **alert**.
- Scenario weights are editorial judgment unless historically calibrated; do not present them as data-derived probabilities.
- Repeated negative evidence with all deltas fixed at zero requires an explicit threshold explanation. Otherwise cumulative slow-burn stress can accumulate outside the score.
- Article counting is not scoring. Deduplicate event identity and date event date, filing/publication date, and first-seen date separately.

## Lean architecture and retirement

If scoring has stopped moving while receipts, validators, mutation flags, shadow states, or approval ledgers remain green, suspect missing ownership before adding another guard.

Use Git history to classify components:

- `RESTORE` a simpler behavior baseline;
- `SALVAGE` later domain improvements;
- `RETIRE` redundant control-plane layers and every active binding;
- `BUILD` only the missing domain owner or atomic publisher.

Keep only unique boundaries such as network safety, exact source identity, atomic durable writers, append-only event history, and duplicate-send protection. A guard that proves nobody changed state is not a substitute for a component responsible for changing it.

## Readability test

Before delivery, a non-specialist reader should be able to answer:

- What changed?
- Compared with what?
- Is it getting better or worse?
- Why does it matter?
- What is the strongest counterpoint?
- Did the thesis, score, regime, or alert actually change?

If the answer requires reading raw filings, score formulas, or pipeline receipts, the briefing has not completed its job.