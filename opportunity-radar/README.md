# Opportunity Radar

Created by Roland Chotika with AI assistance.

**Portables Agentenprojekt mit lokal enthaltenen Fachverfahren; als bereinigter Export veröffentlicht.** Der Radar verbindet LLM-gestütztes Aktien-/ETF-Research mit einem deterministischen SQLite-Kern. Er trennt recherchierte Vorschläge, menschlich aufgenommene Chancen und bestätigte Positionen. Eine Empfehlung bucht keinen Trade.

```text
Scanner oder direkte Idee → Agent + LLM + Research-Tools → Vorschlag
                                                          ↓ Mensch
                 Quartalsbetreuung ← WATCH / READY → bestätigte Position
                                                          ↓
                                               Monatsreview → Mensch → Tradebuchung
```

**Ein intelligenter Agent mit LLM und Werkzeugen ist Produktvoraussetzung; Hermes ist keine Pflicht.** Claude, Codex, OpenClaw, Hermes oder ein anderer Harness können grundsätzlich die Anleitung ausführen; ungeprüfte Kompatibilität wird nicht garantiert. Python-CLI und Offline-Smoke ersetzen weder First Pass/Deep Dive noch Quartals-/Positionsresearch. Einstieg für den Agenten: [AGENTS.md](AGENTS.md). Kanonische Prompts und echte Consumer bleiben enthalten. Die selektive Fachreferenzclosure und bedingten Betreibereingaben: [Runtime und Lesepfade](docs/runtime-dependencies.md).

## Technischer Offline-Einstieg

Zweck: ohne Konten, Livekurse, LLM oder Versand die Zustandsübergänge und Consumer prüfen. Kein Investmentbeispiel und kein Nachweis fertiger Produktinstallation.

Voraussetzungen: Python >=3.11, POSIX für Mailer-Locks; für Scanner/Demo `duckdb`, `huggingface-hub`, `yfinance` gemäß `pyproject.toml`; für Tests zusätzlich `pytest`. Beispiel für eine separat autorisierte Installation mit Paketnetzwerk:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install . pytest
.venv/bin/python -B scripts/offline_demo.py --output demo-output
```

Eine frische Python-3.13-venv wurde mit Paketdownload installiert; Paketimport, 132 echte Tests und zwei Offline-Demos wurden unter Netzwerk-/Schreibsandbox erfolgreich geprüft (lokaler Prüfbericht, nicht Teil des Exports). Ohne Scannerdependencies lässt sich der bestehende Core-Smoke mit einem Python >=3.11 ausführen:

```sh
python3 -B scripts/smoke.py
```

Die Demo erzeugt eine eigene neue SQLite-Datei, selbst erfundene Preisanker, einen ausdrücklich erfundenen Bericht, `reader.md`, `local-mail.md` und `summary.json` im angegebenen neuen Verzeichnis. Ein vorhandenes Ziel wird absichtlich abgewiesen: zum Wiederholen ein neues Ziel wählen. Erwartet: ein Screenhit, Retry `ALREADY_PUBLISHED`, Candidate-Aufnahme zu READY, bestätigte Position, EXIT-Empfehlung ohne Bestandsänderung, anschließend bestätigter synthetischer TRIM auf 8 Einheiten. `local-mail.md` ist nur eine Datei; es wird keine Mail versendet. Systemzeit und absolute Berichtspfade machen Readerbytes zwischen getrennten Läufen unterschiedlich, die fachliche Consumerwirkung bleibt gleich.

```sh
.venv/bin/python -B -m pytest -q -p no:cacheprovider
PYTHONPATH=src .venv/bin/python -B -m opportunity_radar.cli --help
```

## Betrieb und sichere Defaults

- Kein Scheduler und kein Account wird eingerichtet; keine privaten Hermesprofile/Skills/Secrets werden mitgeliefert.
- `HimalayaTransport` verweigert bereits seine Konstruktion ohne `OPPORTUNITY_RADAR_ENABLE_MAIL=1`. Zusätzlich sind expliziter Sender und ein existierender Markdown→Mail-Helper erforderlich. Der Helper und die Mailaccount-Konfiguration sind externe, noch nicht portabel integrierte Voraussetzungen. Kein Versand ist Teil dieses Candidates.
- DB-/Outputdefaults bleiben lokal relativ zum Candidate. Scanner-Caches sind neutrale `state/market-data/`-Pfade. `OPPORTUNITY_RADAR_DB`, `OPPORTUNITY_RADAR_OUTPUT`, `OPPORTUNITY_RADAR_HISTORY_CSV`, `OPPORTUNITY_RADAR_HF_ROOT`, `OPPORTUNITY_RADAR_GLOBAL_ROOT` können explizit gesetzt werden. Kein Originalpfad ist enthalten.
- `observe-live`, `ready-live`, `outcome-live` und Scanner-`main` sind weiterhin echte Livefunktionen. **`--no-publish` ist nicht offline**: Universeabruf und lokale Outputs bleiben möglich. Nur der dokumentierte Offline-Einstieg vermeidet diese Wege. Die Sandbox gehört zum lokalen Proof, nicht zu einer allgemeinen Runtime-Sicherheitsgarantie.
- `--confirmed-by owner` ist ein neutraler lokaler Auditactor, keine Authentifizierung. Nicht für untrusted Multiuserbetrieb.

## Grenzen und Herkunft

Keine Orders, keine Alpha- oder Renditebehauptung. Evaluation zeigt lokale Preisrenditen, nicht vollständigen Total Return/FX. Same-year stale Preise, Kalenderfrische, historische Pending-Reconciliation, volle Providerqualität und vollständige Crash-Durability bleiben begrenzt. Neues `investment_frame` wird nicht durchgehend vom Legacy-Importer erzwungen. Persönlich zurückgestelltes WATCH ohne offene Bedingung hat noch keinen dedizierten Wiederaufnahmebefehl.

Verträge: [Produkt](docs/product-contract.md), [Screening](docs/screening-contract.md), [Positionen](docs/position-lifecycle-contract.md), [Evaluation](docs/evaluation-contract.md), [Delivery](docs/watchdog-mail-contract.md).

Der Projektcode und die eigenen Begleittexte stehen nach ausdrücklicher Freigabe unter der [MIT-Lizenz](LICENSE). Bestehende Rechte und Hinweise zu Drittkomponenten bleiben erhalten: [Herkunft und Lizenzen](PROVENANCE.md). Dieser bereinigte Export wurde mit gesonderter Freigabe als Teil der Collection veröffentlicht.

### Dokumentationsbaseline

Leser: technisch erfahrene Betreiber. Ergebnis: technischen Kern nachvollziehen und fehlende Produktintegration erkennen. Erhalten: Research-/Admission-/Positionsgrenzen, vier aktive Prompts, fünf Verträge, echte Implementierung/Regressionen. Neutralisiert: Personen, Konten, private Pfade und Jobbindungen. Bewusst ersetzt: Live-Schnellstart durch ausdrücklich begrenzten Offline-Proof; Versandaufträge sind im Candidate nicht autorisiert. Quelle: allowlist-basierte Originaldateien, tatsächliche Hermes-Jobdefinitionen und Runtime-Skill. Ergänzt: selektive lokale Fachreferenzen und frische Installation. Offen: tatsächlicher autorisierter Agentenresearchlauf im gewählten Harness, bedingte private Betreibereingaben.
