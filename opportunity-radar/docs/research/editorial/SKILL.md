# Portable reference

Paths in backticks are relative to the package root unless explicitly described as output examples. Read only modules whose triggers apply. Provenance and excluded private inputs: `PROVENANCE.md` and `docs/research/conditional-inputs.md`.

# Editorial Briefing

## When to Use

Use when a daily/recurring source corpus should become a short, decision-ready reader product: an email card, brief, dashboard section, or digest. This is not a retrieval skill and not a title-ranking task. Its job begins after sources and their evidence bodies exist.

## Trigger

Use when a daily/recurring source corpus should become a short, decision-ready reader product: an email card, brief, dashboard section, or digest. This is not a retrieval skill and not a title-ranking task. Its job begins after sources and their evidence bodies exist.

## Product principle

Choose the unit of judgment before drafting. **Daily news evaluates individual events; Weekly analysis evaluates the sector's condition and development over time.** A Daily must not manufacture a sector direction, balance unrelated positive and negative stories, or require broad stress confirmation before treating a concrete negative event as important. Missing new sector data is a knowledge gap, not evidence of stability. A Weekly may synthesize events and stock data into a supported thesis.

Lead readers through the economic meaning, not through the editorial machinery. Make importance visible through selection, order, explanatory headlines and proportionate depth; a complete-looking or equally weighted list is not a briefing.

Keep these layers distinct:

1. **Acquisition:** what was searched, fetched, and extracted.
2. **Evidence:** the full body and canonical source URL supporting an assertion.
3. **Editorial judgment:** what is new, what matters, what is counterevidence, and what is merely context.
4. **Reader projection:** a bounded, legible structure without operational noise.

Never derive a market, product, or operational conclusion from a title, headline, or snippet alone. They can route retrieval but are not evidence.

## Workflow

1. **Read the reader request before building.** If the user asks what the mail/UI should look like, answer the concrete shape first. Do not substitute a Build-Arc, status update, or background result for that answer.
2. **Compact recurring-news format.** Use an explanatory headline and normally one or two short sentences combining the reported development with its economic impact. Give a minor item one brief sentence or omit it; do not give every item equal space. Necessary terms fit within that compact explanation. Extended mechanisms, scenarios and sector synthesis belong to the Weekly; judge the Morning block within the whole mail.
3. **Build an evidence sourcebook.** Resolve each compact source/index row to its persisted full body using canonical URL plus run lineage. Include source, date, URL, and body. Exclude title-only rows from the editorial input; report missing bodies honestly.
4. **Separate newsworthiness and weighting.** Positive/negative direction is not importance. Apply the assigned product’s existing grounding, newsworthiness and weighting responsibilities; do not introduce a new review fleet or a Daily sector-direction counter-reader.
5. **Prefer fewer main points to filler.** A main point needs a current change visible in evidence: new results, a decision, a verified event, or an explicit before/after comparison. For a bounded source-based news briefing, a supported currently reported economic development may also qualify without a separately dated transaction or decision; attribution, an open data period and material provenance uncertainty remain visible. A new publication date does not make an old explainer current. Routine announcements and duplicate coverage do not fill empty slots.
6. **Bind certainty to the specific claim.** A readable secondary report may lead with explicit attribution when its body supports the current development; an absent original is not an automatic weighting veto. Distinguish a technical identity/transport observation from evidence against the article. Research authority comes from the active product mandate, not this editorial skill. A sourcebook-only editor leaves permitted lookups to the existing acquisition/recovery owner. The editor must not initiate follow-up searches or change Sources, coverage, events or scores. Retain sufficiently supported attributed claims and name material unresolved limits without implying that new verification occurred. In a same-corpus replay, retain precise attribution and do not pretend new verification occurred. Prefer a supported second brief item over silently dropping it merely because another event deserves the lead; this is not a quota to fill.
7. **Render special states deliberately.** No usable source, incomplete coverage, editorially unusable evidence, and integrity-blocked input must each have a short, honest reader state. Never fall back to raw title lists merely to fill space.
8. **Exercise the whole reader path.** Verify sourcebook → editorial result → persisted reader state → actual rendered card. A successful writer or Council transcript alone is not reader proof. Delivery checks follow the assigned product contract; this skill adds neither a required orientation heading nor an action section.
9. **Weight economic impact before allocating space.** Identify what changes in capital flows, investor liquidity, credit risk, valuation-risk ownership, refinancing or distribution; establish affected scope, supported scale and event timing. Keep newsworthiness separate from significance: a newly published old event can be economically important without being today's change. For transfers and continuation vehicles, explain who provides cash, who can exit, who retains management and who acquires economic exposure; do not equate investor liquidity with repayment of the underlying loans. For redemptions, distinguish successful payment from the unproven funding source and remaining liquidity. Give substantive mechanisms more depth, administrative transfers brief treatment, and no item a fixed word allowance. Do not build a numerical scoring system just to express priority.
10. **Keep evidence classes distinct.** Separate current events, newly published information about older events, structural research, manager narrative, current market mechanics, and counterevidence before weighting them. Structural mechanism is not current deterioration; interested manager commentary is not a hard stabilizer.
11. **Audit score ownership separately from prose.** When a recurring briefing carries scores, regimes, scenario weights, or alerts, trace evidence → deduplicated events → level/momentum → regime/alert → persisted state. A polished report or a green receipt does not prove the score still updates. Treat numerical scenario weights as editorial judgment unless a documented historical calibration exists.

For the detailed reasoning and lean-retirement pattern, read `docs/research/editorial/references/financial-briefing-analysis-and-scoring.md`.

## Default reader shape

For a Daily news radar, use this unless its explicit reader contract differs:

```text
[Topic · date]

[Most important explanatory headline]
One or two short sentences: concrete change + economic impact.
Include a material limitation only if it changes that impact; source link.
Distinguish publication and event time compactly when needed.

[Next important headline + compact explanation]

[Optional one-sentence minor item; no filler]
```

Do not add a sectoral `Tagesbild`, direction badge or ritual disclaimer that a single event does not prove a broad crisis. Reserve a sector thesis and counterevidence for the Weekly. Do not expose a mandatory `Impact` field: the article itself must convey impact.

Keep acquisition statistics in logs and provenance, not in the owner's Morning Mail: no Radar footer, pipeline labels or unresolved-candidate counts. Preserve a short truthful reader notice when observation or editorial production was unavailable; distinguish that from a successfully evaluated empty selection. A Weekly's explicitly useful editorial evidence-distribution footer is a different concern.

## Reader-facing source weighting for recurring reports

A retrieval or extraction outcome is not an editorial-quality label. Do **not** mark a Daily or Weekly reader product `DEGRADED`, `partial`, or otherwise analytically weak merely because some candidate URLs were blocked, duplicated, stale, irrelevant, or technically unresolved. Those are acquisition dispositions; only evidence admitted into the editorial corpus can support or limit the market judgment.

When a recurring Weekly should make its evidence mix visible, use a compact footer based on **editorially included, mutually exclusive events** — never raw URL attempts or pipeline statuses. State the denominator and ensure the classes sum to it:

- **Leitsignale** — new, thesis-relevant events carrying the weekly delta;
- **Bestätigungen** — corroborating follow-ups without a new threshold;
- **Gegenkräfte & Kontext** — limiting evidence, counterevidence, or bounded background.

Footer template, only when deterministically derived from the final reader allocation:

```text
Wochenbild · n Ereignisse: x Leitsignale (x %) · y Bestätigungen (y %) · z Gegenkräfte & Kontext (z %).
```

The allocation must be a **reader-semantic** one. Do not count raw reconciliation classes (`duplicate_source`, `historical_background`, unresolved candidates, etc.) as if they were report classes: their denominator answers an acquisition question, not an editorial one. If exact reader counts cannot be derived from the final corpus, omit the statistic rather than inventing or hand-maintaining it.

Place it as a muted footer after the conclusion/alert, with no technical caveat.

## Financial-market briefing genre

For financial-market weeklies, preserve analytical depth: a clear central thesis, hard numbers, explicit counterforce and falsification. For the owner, explain the economic meaning before using the numbers as evidence; he is an experienced IT professional, not a financial analyst. Clear language must not remove material mechanisms, comparisons, counterevidence or the product's decision-relevant structure. Use another audience's level only when that audience is explicitly assigned.

- Keep the regime/thesis, weekly delta, counterevidence, score or alert discipline, and watchpoints when they serve the reader.
- Improve only the reader-facing language: technical pipeline states belong in receipts and run logs, while the briefing opens with the market conclusion and its limiting evidence.
- Do not force anecdotal leads, human-interest framing, or prose-only layout if this would remove decision-relevant structure.

## Writing method

Use `docs/research/writing/SKILL.md` as the writing method inside the already assigned editorial step. It does not add an editor, a model call or a post-processing round, and does not change evidence selection, research authority, scores, regimes, alerts or delivery permissions. Existing prompt-bound writers need the relevant concise instructions in their current assignment; loading a skill elsewhere does not reconfigure them.

Complete mails retain Introduction → Body → Summary, with evidence-backed visual orientation where useful. This is not a mail template or graphic requirement for each Daily card: keep its existing explanatory headline and normally one or two sentences. Never invent missing observations to complete a graphic.

## Language rules

- Write for the reader's vocabulary, not the implementation team's. Translate internal labels into product meaning before presenting them: say `Bericht fachlich geprüft, noch nicht versendet`, not `Candidate/Arc/Receipt/Gate`; say `Finanzierungsstress`, not a raw stage identifier. Keep implementation labels out of reader prose unless diagnostics were requested. Explain necessary subject terms in everyday language and include the accurate technical term in parentheses at the first explanation so the owner can recognize it elsewhere. Terms also serve learning, not only an immediate decision; do not invent jargon or repeat the parenthetical definition at every occurrence.
- When the user says the language is too technical, stop the process narration immediately. Restate only `Ergebnis → Bedeutung → nächste Entscheidung` in plain German before doing or reporting more work.
- Write explanatory headings, not copied headlines.
- State the concrete implication plainly and separate evidence from interpretation; reserve aggregate direction for an explicitly assigned synthesis product.
- Comparison words such as “improved”, “deteriorated”, “first”, or “rising” require an explicit comparison in the body.
- Do not infer system-wide sentiment from a single issuer, a PR, or a dramatic commentator.
- If evidence is insufficient, name the specific unresolved claim or coverage limitation; do not turn missing Daily evidence into a market no-signal verdict.

## Pitfalls

- **Title journalism:** Turning headline wording into the conclusion. Fix the evidence path; do not tune title weights.
- **False completeness:** Filling three main points because the layout permits three. Zero, one, or two can be the correct editorial result.
- **Technical takeover:** Letting acquisition failures or scanner metrics become a quality judgment about the reader product. Do not surface them as a caveat when the admitted evidence corpus supports the report; use a source-weighting footer only when its counts are exact and editorially meaningful.
- **Scope narrowing:** Reframing a deliberately broad domain into a narrow issuer/ticker feed because that is easier to summarize.
- **Premature build narration:** Starting implementation discourse when the unresolved issue is simply the desired reader shape.

## Completion proof

Report separately:

- evidence bodies actually available versus source-index rows;
- the Daily's selected events, priority and body-backed economic implications, or the Weekly's sector thesis and counterevidence;
- rendered reader content, including the muted statistics footer when applicable;
- special-state behavior exercised for no-news, unusable-evidence, incomplete-coverage, and integrity-blocked cases.
