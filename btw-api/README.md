# btw_api — bereinigter lokaler Export

**Marktdaten sammeln, Kennzahlen berechnen und aus Google Sheets einen strukturierten Snapshot lesen.** Enthalten ist die bestehende BTC-/MSTR-, Markt-/Sektor- und optionale Macro-Pipeline, keine neue Beispielarchitektur. Der lokale Einstieg verwendet ausschließlich synthetische Daten und benötigt keine Konten.

```text
Live:    Provider → Rowbuilder + Kennzahlen → Google Sheets → Snapshot + Score/Anzeige
Offline: synthetische Serien → dieselben Rowbuilder → Speichertransport → derselbe Consumer
```

Der Projektcode steht unter der [MIT-Lizenz](LICENSE); Rechte an Drittkomponenten und Providerdaten bleiben davon unberührt (siehe `RIGHTS.md`). **Dieser Export liegt bislang nur lokal vor; eine Veröffentlichung ist noch nicht freigegeben.** Originaldaten, Konten, Schlüssel, Scheduler und persönliche Konfiguration sind nicht enthalten.

## Schnellstart ohne Netzwerk und ohne Zugangsdaten

Voraussetzung: vorhandenes Python mit den Paketen aus `requirements.txt`. Tatsächlich getestet wurde Python 3.14.5; die Versionen stehen unten. Aus dem Exportverzeichnis:

```sh
python -B -m examples.offline_pipeline
```

Ergebnis: JSON auf stdout mit `input_kind: SYNTHETIC_ONLY_NOT_MARKET_DATA`, je 1.500 DB-/MARKET_DATA-Zeilen, vollständigem synthetischem Score, 200-Wochen-Durchschnitt und elf Sektor-ETF-Vergleichen. Die Beobachtungsdaten enden fest am 18.10.2026. **Auch die Provider-/Provenienzfelder im Ergebnis sind synthetisch**, nicht Nachweise eines Abrufs. Keine dieser Zahlen ist als Marktinformation nutzbar.

Das Beispiel ersetzt ausschließlich Datenbeschaffung und Sheet-Transport im eigenen Prozess. Es ruft die produktiven `_build_db_rows`, `_build_market_data_rows`, `compute_all`, `sheet_to_df`, `numericize`, den Snapshot-Haupteinstieg und Score-/Display-Consumer auf. Es berechnet nicht heimlich eine zweite vereinfachte Demo. Der Sektor-Stichtag wird fest übergeben; die Macro-Ansicht ist hier bewusst deaktiviert. Die Produktionsmodule werden nicht umgeschrieben.

### Isoliert prüfen (macOS)

```sh
python -B tools/verify_local.py
```

Der Prüfer setzt ein leeres eigenes HOME, ein explizites Export-PYTHONPATH, deaktiviert `.env`/User-Site/Plugin-Autoload und startet Beispiel, Tests und CLI-Hilfe in `sandbox-exec`. Das Betriebssystem verweigert Netzwerkverbindungen und sämtliche Dateischreibzugriffe außerhalb `.verification/`. Ein negativer Verbindungs-/Schreibtest prüft diese Grenzen; geladene Projektmodule müssen unter dem Exportroot liegen. Zwei Beispielausgaben müssen bytegleich sein.

Die vorhandene Python-Umgebung wird nur gelesen, nicht kopiert oder verändert. `.verification/` enthält erzeugte, ausschließlich lokale Prüfergebnisse und synthetische Testdateien; sie gehört **nicht** in einen weitergegebenen Export. Auf Linux ist das Beispiel nutzbar, aber der mitgelieferte OS-Sandbox-Nachweis ist macOS-spezifisch und verweigert die Verifikation ohne `sandbox-exec`.

## Installation und belegte Grenze

Dies ist ein aus dem Quellverzeichnis startbares Projekt, kein publiziertes Python-Paket. Im Ursprung gibt es weder `pyproject.toml` noch `setup.py`; deshalb wird kein erfundener Paket-/Releasevertrag ergänzt. Alle Module mit `python -m ...` aus dem Exportroot ausführen. Der Code verwendet Python-3.10+-Syntax; andere Python-Versionen als 3.14.5 wurden hier nicht getestet.

Eine neue Umgebung würde üblicherweise so eingerichtet:

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
```

**Frische Installation unter macOS mit Python 3.14.5 geprüft:** unveränderte Requirements aus PyPI in eine neue venv ohne globale oder ursprüngliche Projektpakete installiert; `pip check` erfolgreich. Offline-Einstieg zweimal bytegleich, 255 Tests bestanden (14 Warnungen), alle drei CLI-Hilfen erfolgreich. Projektimporte und Dependencyimporte auf Exportkopie bzw. neue venv begrenzt; Offline-Ausführung mit geprüfter Netzwerk-/Schreibsperre. Kein Wheelhouse und kein vollständiger aufgelöster Lockfile werden mitgeliefert; eine frische Installation ohne Netzwerk ist daher nicht belegt. Die Mindestversionsdatei ist kein reproduzierbarer Lock. Direkte Imports benötigen pandas, numpy, requests, gspread, google-auth, python-dotenv und yfinance; pytest ist für die Tests enthalten. Transitive Pakete wie curl_cffi, protobuf, OAuth-/HTTP-Abhängigkeiten kommen aus der jeweiligen Auflösung, nicht aus diesem Export.

Belegte vorhandene Umgebung: Python 3.14.5, pandas 3.0.2, numpy 2.4.4, requests 2.33.1, gspread 6.2.1, google-auth 2.50.0, python-dotenv 1.2.2, yfinance 1.3.0, pytest 9.1.1. Ein fehlender Import ist ein Setupfehler; das Beispiel installiert nichts automatisch und greift nicht auf den Originalquellbaum zurück.

## Livebetrieb: separat und ausdrücklich konfigurieren

**Ein Dry-Run ist nicht offline.** Er kann Provider abrufen und der Daily-Refresh liest schon zur Schema-Prüfung Google Sheets. Nur das oben genannte Beispiel ist credentialfrei/offline. Keine Live-Funktion wurde für diesen Export ausgeführt.

1. `config.example.env` nach `.env` kopieren und nur eigene Werte eintragen.
2. Eigenes Google-Cloud-Projekt mit Sheets- und Drive-API sowie Dienstkonto einrichten. JSON-Schlüssel lokal außerhalb eines weitergegebenen Pakets aufbewahren, `GOOGLE_SERVICE_ACCOUNT_FILE` setzen. Das eigene Spreadsheet dem Dienstkonto freigeben (Editor nur für bewusst aktivierte Schreibläufe).
3. `SPREADSHEET_ID` und für OI/Liquidationen einen eigenen Coinalyze-API-Key setzen. Providerverfügbarkeit, Nutzungsbedingungen, Quoten und gegebenenfalls kostenpflichtige API-Berechtigungen selbst prüfen. Öffentliche HTTP-/Yahoo-Quellen können blockieren oder ihre Formate ändern.
4. Tabellen und Header bewusst vorbereiten: `DB_COLUMNS`, `MARKET_DATA_HEADER`, optional `MACRO_DATA_COLUMNS` sind der positional gebundene Vertrag. Daily lehnt unpassende Header ab; kein automatischer ungeprüfter Schemasprung.

```sh
# Live-Reads/Fetches, keine Sheet-Schreibvorgänge:
python -m src.scripts.run_backfill --dry-run --sheet DB --sheet MARKET_DATA
python -m src.scripts.run_daily --dry-run --lookback-days 5

# Explizit mutierend; erst nach eigener Ziel-/Rechteprüfung:
python -m src.scripts.run_backfill --write --sheet DB --sheet MARKET_DATA
python -m src.scripts.run_daily --write --lookback-days 5

# Lesender realer Consumer des eigenen Sheets:
python -m src.scripts.market_briefing_snapshot
python -m src.scripts.market_briefing_snapshot --sectors-only --as-of 2026-10-18
```

Full-Backfill ersetzt die gewählten Tabellen vollständig; nicht als regelmäßigen Job einrichten. Daily aktualisiert standardmäßig fünf abgeschlossene Kalendertage mit längerem Rechenkontext und Merge-Schutz. `run_daily` und `run_backfill` sind in diesem Export ohne `--write` standardmäßig Dry-Run. Die internen Writer-APIs bleiben absichtlich echte Writer; sie sind keine allgemeine Sicherheitssandbox. Die historischen OI-Wartungswerkzeuge sind weiterhin nur mit `--apply` mutierend; sie sind kein Erstsetup und enthalten fachlich gebundene Migrationszeiträume.

Optionale 30-/90-/180-Tage-Spreadsheets brauchen eigene Ziel-IDs und `WINDOWED_SHEETS_ENABLED=true`. Der bisherige automatische Aufruf eines benachbarten Market-Stress-Projekts ist entfernt. Kein Cron, launchd, Mail, LLM, Upload oder Push wird eingerichtet.

## Produkt- und Datengrenzen

- **DB/MARKET_DATA:** Die Providerclients, historischen/daily Rowbuilder, Kennzahlen, Merge-/Schema-Schutz und Sheets-Persistenz sind enthalten. Live bleibt Sheets die Quelle des Snapshot-Consumers; das Offline-Beispiel führt keinen konkurrierenden dauerhaften Datenspeicher ein.
- **MACRO_DATA:** Collector, Validator, typisiertes Schema, FINRA/NFCI/Fed-Liquidität/HY-OAS/BDC-Familien und Consumer bleiben enthalten. Standardmäßig deaktiviert. Für eine vollständige historische Ausführung fehlen absichtlich die nicht exportierbaren Dateninputs: `src/data/macro/BAMLH0A0HYM2_archive_1996_2021.csv`, dazu `.metadata.json`, der ursprüngliche BDC-Migrationsmanifest und datierte BDC-Exports in `data/inbox/bdc_scores/`. Eine vollständige Macro-Ausführung ist deshalb **nicht sofort einsatzbereit**. Keine Ersatzdaten oder synthetischen Daten werden in den Livepfad eingeschleust.
- Der HY-Archivloader erwartet CSV-Spalten `DATE,BAMLH0A0HYM2`; Metadata müssen `sha256`, `coverage_start`, `coverage_end` passend zum rechtmäßig beschafften Archiv enthalten. Der Reportingpfad referenziert zusätzlich `bdc_scores_initial_migration_manifest.csv`. Vor Macro-Aktivierung Inputs/Rechte und deren Kontinuität klären. Der BDC-Reader erwartet `bdc_scores_YYYY-MM-DD.json`; Schema: `src/config/bdc_scores.schema.json`. Der externe BDC-Produzent ist nicht Teil dieses Projekts.
- Kurze/mangelhafte Historien dürfen fehlende Kennzahlen erzeugen. Funding bleibt mangels dokumentiertem täglichen Settlementvertrag als `held` markiert. Sektor-ETFs sind Preisrendite-Proxies ohne Dividenden, keine offiziellen Sektorindexrenditen. Retrospektive Macro-Historien sind nicht automatisch point-in-time-Daten.
- Snapshot und mechanischer Score sind keine Beratung, Handelsausführung oder Versandpipeline. Die separate Producer-Arc-Linie und private Weekly-/Hermes-Consumer wurden nicht zusammengemischt. Ihre abweichenden Snapshot-Felder werden nicht als vorhanden behauptet.

## Herkunft und Prüfbericht

Kanonische Quelle dieses Candidates ist Commit `4d4012c329be6c9b6fe0ffd156031f36a35fd42e` von btw_api. Die Alternative `f8c6a8f6e5f2a16b4e86e54ddbe111a6f8e6df0f` wurde nicht gemergt. `export-allowlist.txt` benennt jede aus dem Commit übernommene Datei. Für diesen Export wurden Konfigurationsvorlagen neutralisiert, schreibende CLI-Aufrufe auf explizites `--write` umgestellt und ein privater Nachbarprojektaufruf entfernt. Das synthetische Offline-Beispiel, die Exportprüfungen und diese Einstiegshilfe wurden ergänzt. Dieser Export verändert keine Installation oder Quelldatei außerhalb seines Verzeichnisses.
