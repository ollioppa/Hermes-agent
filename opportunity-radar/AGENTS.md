# Agenteneinstieg

Du bist der ausführende intelligente Agent. Der Code ist der deterministische Unterbau, kein LLMrunner. Nutze deinen vorhandenen Harness und eigene autorisierte Werkzeuge; keine Hermes-Pflicht, keine neue Adapterarchitektur. Die vollständigen ausgewählten Fachverfahren sind lokal unter `docs/research/` lesbar; die bedingten privaten Eingaben und die Lizenzhinweise sind in `docs/runtime-dependencies.md` abgegrenzt. Melde fehlende Referenzen, statt ihre Regeln zu erfinden oder einen Fixturelauf als Research auszugeben.

## Vor dem Start

1. Lies README, Produktvertrag und den für den Auftrag relevanten Screening-/Positions-/Evaluationsvertrag. Lies `docs/runtime-dependencies.md` und `docs/research/stockpicking/SKILL.md`; folge vor dem jeweiligen Auftrag allen passenden Modultriggern. Für Berichte zusätzlich `docs/research/editorial/SKILL.md`, `docs/research/writing/SKILL.md` und `docs/research/citations/SKILL.md`.
2. Arbeite im Paketroot mit Python >=3.11 und den Dependencies aus pyproject. Wähle eine eigene DB und Outputbereiche. Richte keine Jobs, Konten oder Sendefreigaben ohne ausdrückliche Zustimmung ein.
3. Kläre den Auftrag: technischer Offlineproof, direkter Researchauftrag, fälliger Candidate, Quartalsbetreuung oder Positionsreview. Recherche benötigt LLM, Suche/Extraktion öffentlicher Primärquellen, Dateioperationen und tatsächlich ausgeführte Berechnungen. Einen fachlichen Auftrag nicht auf CLI-Eingabevalidierung verkürzen.
4. Nutze `PYTHONPATH=src python -m opportunity_radar.cli --help` und die Hilfe des jeweiligen Subcommands. Das `python` muss dein vorbereiteter Interpreter sein. Beispiele in den Prompts verwenden `.venv/bin/python`; ersetze nur den Interpreter/Paketroot und deine explizite DB, nicht die fachlichen Regeln.

## Workflow und Inputs/Outputs

- **Scanner:** rechtmäßig bezogene Markt-/Universeinputs → `scripts/run_trend_screening.py` → Screens/Hits/OPEN-Candidates. Der echte Scanner ist netzwerkfähig. Offline nur `scripts/offline_demo.py` verwenden.
- **Candidate:** lies `prompts/autonomous-candidate-research.md`. `next-candidate --db DB` liefert Identität, Episode und Arbeitsstand. First Pass, danach gegebenenfalls vollständiger kanonischer Deep Dive. Schreibe einen belegten Bericht; `candidate-work` bei Budgetpause, ansonsten exakt eine gebundene Disposition über `candidate-decision`. Lies `show-candidate --candidate-id ID --db DB` zurück. Kein automatischer WATCH/READY-Aufstieg.
- **Direkte Idee:** kein erfundener Scanner-Candidate. First Pass für normale Ideen, bei ausdrücklichem Deep-Dive-Auftrag direkt das vollständige Mandat `prompts/stockpicker-deep-dive-v2.7-2026-10-27.md` lesen. Bericht und strukturierter Handoff, noch keine Aufnahme.
- **Menschliche Aufnahme:** nur nach ausdrücklichem Auftrag `promote-candidate` bzw. `import-case`, vollständiger Review/Snapshot/Quellen-Handoff; WATCH braucht eine echte Bedingung, READY ist kein Kauf. Candidateaufnahme muss ID/Episode erhalten. Der Datenbankschreiber bindet historische Fälle und Kapazitätsgrenzen.
- **Quartal:** `prompts/quarterly-watch-letter.md` → `render_quarterly_watch_context.py` → gebundene WATCH/READY/Candidate-Gruppen → begrenzte neue Evidenz → redigierter Brief plus vollständiges Manifest. Keine Status-/Bestandsmutation. Kein Versand im Candidate.
- **Positionen:** `prompts/monthly-position-review.md` → aktuelle Position und Baseline lesen → öffentliche Evidenz → `record-position-review` → vollständiger Monatskontext/Brief/Manifest. HOLD/TRIM/EXIT/NO_DECISION sind Empfehlungen. Nur ausdrücklich bestätigte ausgeführte Ereignisse über `confirm-position-event --confirmed-by owner` ändern Bestand.

## Grenzen

Quellen und echte Marktbeobachtungen niemals durch Demo-Inputs ersetzen. Keine Investmentqualität aus grünen Tests ableiten. Kein automatischer Trade, EXCLUDE oder Statusaufstieg. Fehlende Quellen, Rechte, Fachreferenzen und unpassende Preisnotierungen offen lassen. Kein LLM-, Netzwerk- oder Versandlauf wird durch die Installation dieser Dateien autorisiert. Der technische Offlineproof ist ein Teilnachweis; Harnesskompatibilität ist nicht pauschal getestet.
