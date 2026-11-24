> Lokale, neutralisierte Vorlage. Kein aktiver Job, kein LLM-Aufruf, keine Versandfreigabe.

# Autonomous candidate research

## Auftrag

Bearbeite genau eine fällige Recherche bzw. ausdrücklich wiedervorgelegte Episode. Nach fachlichem Abschluss darfst du höchstens eine Candidate-Entscheidung schreiben; Budgetpausen sind nur Arbeitsstände. Du darfst keinen Radar-Fall, Radar-Status, Bestand, Kauf oder Verkauf verändern.

## Produktiver Einstieg

Kein Scheduler wird mitgeliefert. Dieser Auftrag wird nur ausdrücklich manuell verwendet.

## Eingefrorener Deep Dive

- Datei: `prompts/stockpicker-deep-dive-v2.7-2026-10-27.md`
- SHA-256: `8dfee76b20da642185e80befe2d2fb36d0ddf0690c1e6e19fe43b4d1938d3717`

Prüfe Pfad und Hash vor dem Research. Nur die oben gebundene v2.7 ist aktiv. Bei einem anderen Pfad — ausdrücklich auch historischen Mandaten bis v2.6 — oder einer Hash-Abweichung: stoppe ohne Entscheidung. Wiederhole, paraphrasiere oder ergänze die fachlichen Deep-Dive-Regeln nicht.

## Ablauf

1. Nutze im Repository `PYTHONPATH=src .venv/bin/python -m opportunity_radar.cli next-candidate --db state/opportunity_radar.sqlite3`. Bei `NONE` keine Entscheidung und kein Bericht.
2. Lies `research_history`, `report_handoff` und einen vorhandenen `metrics.research_work`-Stand zuerst. Übernimm Quellen und offene Arbeit, prüfe das Delta zum damaligen Ablehnungsgrund; nicht von vorne akquirieren. Fehlende alte Berichte offen benennen.
3. Ein kurzer First Pass prüft Signalverzerrung, tragfähigen Motor und stärkste wirtschaftliche Gegenkraft. Ist nur das Trendargument verzerrt, aber eine eigenständige fundamentale Chance erkennbar, untersuche dieselbe Firma unabhängig vom Trend weiter. Bezeichne die Signalverzerrung ausdrücklich; erfinde oder repariere keine Scannerepisode. Ohne überlebende unabhängige Chance: SCREEN_DISTORTED. Wirtschaftlich nicht tragfähig: DEFER_EPISODE.
4. Bei überlebender Chance lies den gebundenen vollständigen Deep Dive und führe ihn aus. Zeit-/Toolbudget ist kein wirtschaftlicher Ablehnungsgrund und kein erfundener Informationsblocker. Endet die Arbeit vorher, schreibe einen fortsetzbaren Quellen-/Arbeitsbericht und speichere nur `candidate-work --candidate-id ID --signal-date FIRST_ENTRY_MONTH --report-path PATH --source-as-of YYYY-MM-DD --resume-from "konkret fehlende Arbeit"`. Keine wirtschaftliche Disposition in diesem unterbrochenen Lauf; nächster Lauf setzt denselben Stand fort.
5. Nach echtem Abschluss: DROP → DEFER_EPISODE; genau ein entscheidender, derzeit nicht verfügbarer Beleg → RESEARCH_INCOMPLETE mit Wiedervorlage; vollständiger positiver Vorschlag → AWAITING_USER. Zukunftsunsicherheit nicht pauschal in fehlende Daten umdeuten. Research-Revisit ist keine WATCH-Promotionbedingung.
6. Bericht: `output/reviews/automated/YYYY-MM-DD-SYMBOL.md`, mit Urteil, Informations-/Preisanker, eigener Zukunft und Quellen. Bei preisbezogener Ablehnung dürfen DEFER_EPISODE-Entscheidungen eine begründete Datums- oder Ereignis-/Preiswiedervorlage erhalten. Datierte Wiedervorlagen werden fällig; Ereignis-/Preistrigger werden nicht automatisch geraten, sondern nur durch `next-candidate --candidate-id ID --confirmed-by owner` freigegeben. Kein neuer Überwachungsdienst. Wiederprüfung derselben Research-Episode umgeht nie die Aufnahmegrenze archivierter Radarfälle.
7. Speichere höchstens eine fachlich abgeschlossene Entscheidung mit `candidate-decision`, `--decided-by autonomous-research`, tatsächlicher `--candidate-id`, unverändertem `--signal-date` und geschriebenem Bericht. Budgetpause nutzt ausschließlich candidate-work. Identische Wiederholung bleibt ein Retry, keine neue Episode.
8. Lies `show-candidate --db state/opportunity_radar.sqlite3 --candidate-id ID` mit der vorher ausgewählten Candidate-ID zurück: stable_identity, Entscheidung bzw. Arbeitsstand, Episode, Revisit und Reportpfad. Bei Abweichung keine zweite Entscheidung. Symbol ist nur Leselabel, nicht die Identität. Vollständige negative und direkte Berichte bleiben per `research-history` auffindbar, ohne synthetische Candidateaufnahme.

## Vier automatische Ergebnisse

- `DEFER_EPISODE`: aktuell nicht attraktiv; Episode archiviert, konkrete begründete Wiedervorlage bleibt möglich. Keine automatische Radaraufnahme.
- `RESEARCH_INCOMPLETE`: genau ein entscheidender Informationsblocker; Candidate bleibt bis zur Wiedervorlage offen, aber nicht erneut fällig.
- `SCREEN_DISTORTED`: Kurssignal wirtschaftlich nicht interpretierbar; Episode wird ohne negatives Unternehmensurteil archiviert.
- `AWAITING_USER`: vollständiger Deep Dive ist entscheidungsreif; Candidate bleibt offen für Owner.

`EXCLUDE` ist ausschließlich Owner vorbehalten. Kein Ergebnis ist ein `WATCH`-, `READY`- oder Kaufentscheid.

## Schreibbefehl

```text
PYTHONPATH=src .venv/bin/python -m opportunity_radar.cli candidate-decision \
  --db state/opportunity_radar.sqlite3 \
  --symbol SYMBOL \
  --candidate-id SELECTED_ID \
  --signal-date FIRST_ENTRY_MONTH \
  --decision DISPOSITION \
  --reason "..." \
  --report-path "output/reviews/automated/YYYY-MM-DD-SYMBOL.md" \
  --reader-text "..." \
  [--revisit-after YYYY-MM-DD | --revisit-trigger "..."] \
  --decided-by autonomous-research
```

## Stop-Regeln

- Kein zweites Unternehmen untersuchen.
- Keine fehlenden Fakten erfinden.
- Eine leicht beschaffbare Kennzahl ist kein `RESEARCH_INCOMPLETE`.
- Mehrere offene Kernfragen sind kein einzelner Wiedervorlagegrund.
- Kein Radar- oder Positionsobjekt anlegen oder ändern.
