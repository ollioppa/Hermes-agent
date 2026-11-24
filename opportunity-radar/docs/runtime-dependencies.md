# Portables Agentenprojekt: Harness stellt die Werkzeuge

Das Paket enthält den deterministischen Kern, vier kanonische Arbeitsaufträge und die selektiv exportierten fachlichen Verfahren. Claude, Codex, OpenClaw oder Hermes können die Dateien über ihren eigenen Harness einbinden. Kein neuer Runner, Adapter oder Hermeszwang. Plattformübergreifende Agentenläufe wurden nicht durchgeführt; der Offlineproof ist kein Researchqualitätsnachweis.

## Verbindlicher Lesepfad

Alle Backtickpfade sind relativ zum Paketroot. Der ausführende Agent liest vor Research `docs/research/stockpicking/SKILL.md` und folgt dessen tatsächlichen Triggern; kein bloßes Laden aller Texte auf Vorrat.

| Auftrag | Lokale fachliche Bindung |
|---|---|
| Idee/First Pass/Candidate | `docs/research/stockpicking/references/intake-and-screening.md`; für persistierte Candidates zusätzlich `docs/research/stockpicking/references/radar-and-recurring-operations.md` und `prompts/autonomous-candidate-research.md` |
| Full Deep Dive/ökonomischer Vergleich | Vollständig `prompts/stockpicker-deep-dive-v2.7-2026-10-27.md` und `docs/research/stockpicking/references/economic-investigation.md` |
| Fachliche Sonderfälle | `docs/research/stockpicking/references/situational-review.md`; bei Automobiltransition bzw. SOTP die dort gebundenen vollständigen Branchenverfahren |
| Quartalsbetreuung | `prompts/quarterly-watch-letter.md` und Radar/Recurring-Modul; begrenztes Evidenzdelta, kein automatischer neuer Deep Dive |
| Positionen/Monatsreview | `prompts/monthly-position-review.md` und `docs/research/stockpicking/references/owned-position-review.md`; gespeicherte Baseline zuerst |
| Methodenprüfung oder Szenarienvergleich | `docs/research/stockpicking/references/method-validation.md`; bei neuen Linsen vollständiges Incremental-Lens-Protokoll, keine neue Aufnahmebedingung |
| Bericht und Quellen | `docs/research/editorial/SKILL.md`, `docs/research/writing/SKILL.md`, `docs/research/citations/SKILL.md`; zugehörige Detailreferenzen nach Trigger |
| Sektorübergreifende Mechanismen | `docs/research/mechanisms/SKILL.md` und dessen vollständige Matrixreferenz |
| Thematische These, Kreditregime, Portfoliofit | `docs/research/conditional-inputs.md`; für Supercycle zusätzlich `docs/research/supercycle/SKILL.md` |

Der vollständige Deep Dive wurde in diesem Closure-Schritt nicht verändert oder gekürzt. Seine bereits neutralisierte Paketfassung ist mit SHA-256 `8dfee76b20da642185e80befe2d2fb36d0ddf0690c1e6e19fe43b4d1938d3717` gebunden. Fachverfahren ergänzen ihn, setzen aber kein zweites Auswahlmodell. Konflikte ausdrücklich melden statt eine Regel still zu überschreiben.

## Tatsächliche externe Voraussetzungen

Python >=3.11, Dependencies aus `pyproject.toml`, ein autorisierter Agent mit LLM, öffentlicher Suche/Extraktion, Dateioperationen und tatsächlich ausgeführten Rechnungen. Der Betreiber bindet Workdir, eigene DB, Outputbereiche und Werkzeuge ein. Keine fremden Sessions, Profile oder Erinnerungen laden. Scheduler und Versand sind separate Betreiberentscheidungen, nicht Teil der Installation.

Quellenledger: `docs/research/citations/scripts/sources.py` ist der vorhandene stdlib-Ledger mit neutralisiertem Default `state/citations/ledger.json`; explizit `--ledger PATH` oder `RADAR_CITATION_LEDGER` verwenden. Keine Hermes-Home-Hilfsbibliothek nötig. Quellenkette und Evidenceprüfung bleiben erhalten.

Private dynamische Kredit-/Themenzustände, Bestände und historische Methodenbeweise sind eng in `docs/research/conditional-inputs.md` abgegrenzt. Das sind bei passenden Aufträgen echte notwendige Eingaben, keine mitgelieferten oder erfundenen Daten. Ohne solche Trigger ist die lokale methodische Referenzclosure vorhanden. Ohne LLM/Quellenzugang ist nur der technische Kern prüfbar.

Die ursprünglichen gebundenen Skills wurden read-only selektiv übernommen; private projektübergreifende Pfade und Integrationsanweisungen wurden neutralisiert. Ursprüngliche Jobzeiten/Modellpins sind keine portable Fachregel und werden nicht als erforderliche Konfiguration übernommen. Mail bleibt fail-closed; MIT ist für diesen Export freigegeben; eine Veröffentlichung benötigt weiterhin die gesonderte Inhaltsfreigabe, siehe `PROVENANCE.md`.
