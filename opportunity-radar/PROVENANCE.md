# Herkunft, Rechte und Datenabgrenzung

## Eigene Projektdateien

Source, Regressionstests, statische Screeningkonfiguration, vier aktuelle Prompts und fünf Verträge stammen aus dem lokalen Opportunity-Radar-Projekt, selektiv kopiert und neutralisiert. Die exakte lokale Zuordnung/Hashes stehen nur im nicht zu verteilenden Reviewbericht und `.verification/source-manifest.json`.

Roland Chotika hat MIT ausdrücklich für diesen lokalen Radar-Export freigegeben; siehe LICENSE. Die ursprünglichen Projektquellen enthielten keine Projektlizenz. Die Freigabe gilt für die Rechte, die der Lizenzgeber vergeben kann; bestehende Rechte und Notices von Drittkomponenten sowie Provider-Datenrechte bleiben unberührt. Sie ist keine Freigabe zum Upload oder zur Veröffentlichung.

Neue Dateien dieses Candidates: README, AGENTS, Runtime-/Herkunftsdokumentation und Offline-Demo. Auch ihnen wird hier keine erfundene Freigabelizenz gegeben. Der Original-Freeze wurde weder kopiert noch geändert; diese Kopie beansprucht nicht dessen ursprüngliche Hashbindung.

## Dependencies, nicht eingebettet

Gelesene Metadaten der tatsächlich für den Proof verwendeten Installation:

| Paket | Version | lokale Lizenzmetadaten |
|---|---|---|
| duckdb | 1.5.5 | MIT-Klassifikator |
| huggingface-hub | 1.30.0 | Apache-2.0 |
| yfinance | 1.7.0 | Apache-2.0 |
| pytest | 9.1.1 | MIT |

Keine dieser Bibliotheken oder ihre Binärdateien werden mitgeliefert. Das ist keine Prüfung aller transitiven Rechte/Notices und keine Zusage für andere später aufgelöste Versionen. `pyproject.toml` bewahrt die bestehenden Versionsbereiche; eine frische Python-3.13-Installation mit Paketdownload wurde zusätzlich ausgeführt (Versionen und vollständiges Installationslog im nicht verteilten lokalen Proof). Harness, LLM, Recherchetools und gegebenenfalls Mailtransport sind getrennte externe Voraussetzungen.

## Test- und Demodaten sind nicht dasselbe

`scripts/offline_demo.py` erzeugt neue, ausdrücklich erfundene Firma/Preishistorie/Position/Research-Prosa. Kein privater Researchbericht oder Marktcache wurde hierfür kopiert. Die Demo belegt technische Consumerwirkung, keine Researchqualität.

Die bestehenden Regressionen sind dagegen **abgeleitete Alt-Testquellen**, keine pauschal neu synthetisierten Daten. In den beiden JSON-Schemafixtures wurden Firmenbeschreibung, wirtschaftliche Aussagen, Quellenlinks und Watchprosa ersetzt. Testkompatible Symbole, Daten, Providerlabels und numerische Referenzkonstanten blieben erhalten. Insbesondere historische Zahlen wie 400.84/765.96 sind übernommene Testkonstanten und werden nicht als neu erfundene Preise ausgegeben. Einzelne API-Parserfixtures/Sourcekonstanten sind ebenfalls Teil der bestehenden Testimplementierung. Es wurde kein privater Datenbankbestand, Brokerexport, Mailreceipt, historisches Researchverzeichnis oder Kurskorpus übernommen. Gewöhnliche numerische Regressionkonstanten sind kein pauschaler Exportblocker. Es wurden keine konkreten privaten Bestandsdaten in diesen Fixtures identifiziert; private Originalbestände und der persönliche ausgearbeitete Investmentfall bleiben ausgeschlossen.

Live-Marktdatenrechte bleiben getrennt: HF-Dataset-/Bibliothekslizenzen überschreiben keine Yahoo-/Emittenten-/Exchangebedingungen. Kein Markt- oder Universe-Datendump ist Bestandteil des Pakets. Statische Instrumentlisten in `config/` sind Konfiguration, keine Holdingsdaten eines Nutzers.

## Selektiv exportierte Fachverfahren

Unter `docs/research/` liegen neutralisierte Ableitungen tatsächlicher lokaler Fachquellen, keine neu erfundenen Ersatzmodelle:

| Exportbereich | Ursprüngliche Quelle | Auswahl / Rechtehinweis |
|---|---|---|
| stockpicking | stockpicking-research-review, Version 2.0.0 | Router und neun Verfahrens-/Branchenreferenzen vollständig, private Fallstudie ausgeschlossen; keine Lizenzdeklaration in der Quelle |
| editorial | editorial-briefing, Version 1.0.0 | Einstieg und financial-briefing-analysis-and-scoring; Quellmetadaten: author BananaHermes, license MIT |
| citations | grounded-citations, Version 1.2.0 | Einstieg, citation-formats und sources.py; Quellmetadaten: author Hermes Agent + Teknium, license MIT; unveränderte Ledgerlogik, nur lokale Pfad-/Umgebungsbindung statt Hermes-Home |
| mechanisms | economic-mechanism-audit, Version 1.1.0 | Einstieg und rent-fragmentation-and-transmission; created_by BananaHermes, keine Lizenzdeklaration |
| supercycle | supercycle-thesis, Version 1.1.0 | Verfahrensrouter, nicht private These/Langmemo; created_by BananaHermes, keine Lizenzdeklaration |
| writing | documentation-guide, Version 1.0.0 | Vollständige operative Schreibmethode; private Adaptationsgeschichte ausgeschlossen, keine Lizenzdeklaration |

Private Namen, absolute Pfade, persönliche Ausschlusspräferenzen, konkrete private Fall-/Bestandsdaten und fremde produktive Jobbindungen wurden entfernt oder als ausdrücklich benötigte Betreibereingabe abgegrenzt. Keine ganze Skillbibliothek kopiert. Quellhashes, Zielhashes und die lokale Zuordnung liegen in `.verification/domain-source-manifest.json`; portable Zielhashes und Quellenkennungen in `docs/research/PROVENANCE.json`. Der kanonische Deep Dive blieb in diesem Schritt bytegleich.

Die MIT-Felder einzelner Quellen werden als Herkunftsinformation erhalten, nicht als pauschale Rechtefreigabe aller Dateien ausgelegt. Die Projektlizenz MIT wurde durch ausdrückliche Entscheidung für Radar ergänzt, nicht automatisch von einem anderen Projekt übertragen. Vor Veröffentlichung sind Rechte und erforderliche Notices der ausgewählten Ableitungen zu bestätigen.

## Nicht verteilen

`report.md`, `.verification/` und alle lokal erzeugten Demo-/State-/Outputverzeichnisse gehören nicht in ein späteres Paket. `EXPORT_FILES.txt` ist die explizite Paketdateiliste. Keine `.git`, `.env`, `.venv`, privaten Skills/Accounts/Sessions, Freeze-/Git-Historie, DBs oder Researcharchive hinzufügen.
