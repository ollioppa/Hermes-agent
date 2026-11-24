> Export-Vertragsreferenz, kein Nachweis aktiver Jobs oder produktiver Zustellung. Persönliche Betriebsbindungen wurden entfernt.

# Produktvertrag v0.1

> **Statushinweis:** Kandidaten-Research, Opportunity Radar und Positionsakte sind produktiv. Research liefert Entscheidungsvorlagen; nur Owners bestätigte Entscheidung verändert Aufnahme oder tatsächlichen Bestand. Der Quartalsbrief betreut WATCH und READY, der Monatsbrief gehaltene Positionen.

## Versprechen

Der Stockpicker findet und betreut attraktive asymmetrische Aktien-/ETF-Chancen gegenüber dem S&P 500 über eine begründete anfängliche Haltedauer von 1–5 Jahren. Defensive Qualität allein ist kein Treffer. Eigene fehlbare Zukunftsprognose, Marktgegensatz, Aktionärswert-/Kapitalverwendungsbrücke und plausibler Dauerschaden tragen das Urteil; keine erzwungenen Kaufcalls. Der Radar verdichtet diese Fälle, ohne sichere Upside, bewiesenes Timing oder bereits validierte Outperformance zu versprechen.

## Zustände

- `INBOX`: Idee, noch kein aktiver Case.
- `WATCH`: Review vollständig; ein konkret benannter Baustein fehlt oder Owner hat einen bisherigen READY-Fall ausdrücklich aus persönlicher Priorität zurückgestellt.
- `READY`: entscheidungsreif, kein Kaufauftrag.
- `INVALIDATED`: These oder Asymmetrie gebrochen.
- `ARCHIVED`: diese Gelegenheit bewusst beendet; kein dauerhafter Ausschluss des Wertpapiers.

Maximal acht aktive WATCH/READY, maximal drei READY. Pro Symbol gibt es höchstens einen nicht archivierten Fall. Eine nach Archivierung neu bestätigte Gelegenheit erhält eine neue Case-ID und ihren eigenen Review-/Schatteneinstieg; die alte Case-ID bleibt archiviert und wird nicht zurückgesetzt. Quellen, Snapshots, Auswertungen und tatsächliche Bestandslinks bleiben bei ihrer ursprünglichen Case-ID.

## Pflichtkern

Motor; Sektor-/Makroumfeld und Übertragung; relative operative Stärke; eingepreiste Zukunft; Base/Upside/Dauerschaden relativ zu SPY; Gegenpfad; Falsifikator; konkret fehlender Baustein.

Aktien und ETFs werden nach dem kanonischen Deep Dive v2.7 untersucht. Seine aktive fachliche Authority ist ausschließlich `prompts/stockpicker-deep-dive-v2.7-2026-10-27.md` mit SHA-256 `8dfee76b20da642185e80befe2d2fb36d0ddf0690c1e6e19fe43b4d1938d3717`. Runtime-Aufträge dürfen ihn aufrufen, aber nicht paraphrasieren, kürzen oder durch einen zweiten Deep-Dive-Prompt ergänzen. Historische Mandate bis v2.6 bleiben ausschließlich historische Evidenz und sind keine zulässigen Runtime-Pfade.

Für neue Aktienreviews ist `customer_economics` ein einzelner strukturierter Teil des bestehenden Reviews, kein neues Modell. Er prüft datiert die Vorregime-, Sonderregime- und Normalisierungsphasen, Wachstumskomposition, Preis relativ zum Kundennutzen, Support Intensity sowie Herkunft und Verwendung der Marge. Rent Quality bleibt eine begründete qualitative Synthese ohne Score, exklusives Enum oder automatische Statuswirkung. Bestehende gespeicherte Reviews bleiben ohne Migration lesbar; ETFs erhalten diesen Aktienblock nicht.

## Zeitvertrag

Erstreview, Quellen, Reviewkurs, SPY, Sektorbenchmark und Schatteneinstieg werden vor WATCH oder READY versiegelt. Spätere Reviews sind neue Versionen. Eine Erstaufnahme in WATCH braucht eine konkrete Preis-, Event-, operative, Regime-, Struktur- oder Reaktionsbedingung; eine persönliche Rückpriorisierung aus READY ist die unten beschriebene Ausnahme. READY entsteht entweder atomar aus genau einer offenen WATCH-Bedingung, ihrer dokumentierten Erfüllung und einem neuen, stichtagsgleichen Case-/SPY-/Sektor-Snapshot-Satz oder durch Owners bestätigte direkte Übernahme eines bereits vollständig entscheidungsreifen Kandidaten mit vollständigem Review, Quellen und stichtagsgleichem Snapshot-Satz. Eine direkte READY-Übernahme darf keine künstliche WATCH-Bedingung erzeugen und zählt gegen die Grenze von höchstens drei READY-Fällen.

## Reader

### Persönliche Rückpriorisierung

`deprioritize --confirmed-by owner` erlaubt ausschließlich READY → WATCH mit dokumentiertem Prioritätsgrund. Dabei entsteht keine erfundene fachliche Bedingung; Reviews, Schatteneinstieg und frühere READY-Snapshots bleiben unverändert. Der Reader und der Quartalskontext führen den Grund mit. Eine solche Rückstufung ist keine Verschlechterung der Unternehmensthese. Erstaufnahmen in WATCH benötigen weiterhin eine echte offene Bedingung; automatisches Wiederhochsetzen ist ausgeschlossen. Erneute READY-Aufnahme benötigt eine separate menschliche Entscheidung und einen dafür geeigneten Aufnahmeweg, nicht eine als erfüllt deklarierte Scheinbedingung. Kapazitätsgrenzen bleiben unverändert.

READY vor WATCH vor INBOX, danach INVALIDATED mit Grund. Der Reader zeigt die berechnete lokale Preisbewegung seit Review gegen SPY und Sektor sowie die Beobachtungsdauer. Aktuelle Beobachtung und historische Referenz werden mit Datum/Währung getrennt; nur passende gebundene Reihen werden ausgewertet. Gespeicherter Researchstand, Bericht und Wiedervorlage sind in der Inbox sichtbar, ohne Legacy-Labels als neu validierten Deep Dive auszugeben. Höchstens acht aktive Fälle. Keine breite Tabelle, kein Ops-Log, kein Output bei identischem semantischem Inhalt.

## Watchdog und Mail

Ein deterministischer Watchdog beobachtet Preis, Zeit, Relativbewegung, Quellenalter und Datenfrische. Der erste Lauf setzt nur eine Baseline; nur Signalwechsel erzeugen Event-Mails. Ein separater Quartalsbrief prüft WATCH/READY und offene fertige Vorschläge als begrenztes Delta: gespeicherte These/Bedingung/Falsifikator, heutige kompatible Preisgrundlage, ursprünglicher Endpunkt und verbleibende Asymmetrie gegen SPY in EUR. Geschäft intakt ist keine automatische Bestätigung heutiger Attraktivität; verbrauchte Chance verlangt erneute menschliche Prüfung. Fertige, aktuell gebundene Kandidaten werden getrennt eingeordnet. Ein ausdrücklich mit einer ACTIVE-Position verknüpfter READY-Fall gehört ins Monatsprodukt. Fehlende Verknüpfung beweist keinen Nichtbesitz. Eine alte READY-Einordnung bestätigt keine unbelegte heutige Kaufbarkeit; historische Referenz und passend belegte aktuelle Preisgrundlage bleiben getrennt. Weder Watchdog noch Quartalsbrief dürfen Status oder Bestand verändern.

Der Watchdog prüft nur Fälle mit einer gespeicherten Watchdog-Regel. Ohne bestätigte Regel besteht trotz Kursaktualisierung keine quantitative Eventabdeckung. Individuelle Regeln bleiben ausdrücklich zu bestätigen; sie werden nicht aus einem Status oder diesem Quartalsreview erfunden. Die fundamentale Quartalsbetreuung ist davon unabhängig. Fehlende individuelle Eventregeln werden nicht automatisch ergänzt. Kursbeobachtung folgt der ursprünglichen Notierung/Währung mit explizit passender Währung/Notierung; inkompatible historische Zeilen werden nicht umetikettiert.

## Screening-INBOX

Das Screening ergänzt den Radar um eine begrenzte Kandidaten-INBOX. Automatische Runs dürfen nur Screening-Evidenz, Hits und neue `OPEN` Kandidaten schreiben. Sie dürfen keine bestehenden Case-Zustände, Reviews, Watch-Bedingungen, Snapshots oder Transitionen ändern. Maximal zehn unvollständige aktive Researcharbeiten einschließlich Budgetpause/RESEARCH_INCOMPLETE; fertig vorgelegte AWAITING_USER bleiben sichtbar, zählen aber nicht gegen diese Arbeitsgrenze.

US-Aktien, europäische Aktien und kuratierte ETFs werden getrennt attribuiert. Die US-Lane `TREND_NORMALIZATION` nutzt fünf Dezember-Schlusskurse, einen positiven absoluten OLS-Trend, einen Run ab 130 % und die spätere Research-Zone bis 110 %. Sie ist ein Review-Grund, kein Score und keine Empfehlung. WATCH, READY, Archivierung, Invalidierung und Exit bleiben menschlich bestätigte Aktionen.

Nach dem Screening läuft Research ohne Zwischenfreigaben: ein begrenzter First Pass und bei tragfähigem Motor ein Deep Dive. Das Ergebnis ist genau eine Candidate-Disposition: `DEFER_EPISODE`, `RESEARCH_INCOMPLETE`, `SCREEN_DISTORTED` oder `AWAITING_USER`. Nur der letzte Schritt zu WATCH/READY bleibt bei Owner; Research schreibt nie einen Radar-Status. Dauerhafte Ausschlüsse sind ausschließlich menschlich, episodisches Parken wird mit Begründung gespeichert und vom nächsten Screening respektiert.

Der Scanner ist nicht der einzige Eingang. `Stockpicker: X` überspringt Scanner und Candidate-Inbox, nutzt den kurzen First Pass und läuft bei tragfähigem Motor ohne Zwischenfreigabe in denselben Deep Dive. `Deep Dive: X` startet ihn sofort. Diese direkten Wege erzeugen nicht nachträglich eine Scanner-Episode und verändern ohne Owners ausdrückliche Entscheidung weder Radar noch Bestand.

## Gehaltene Positionen

Die produktive Positionsakte folgt `docs/position-lifecycle-contract.md`: belegte Bestandsdaten und bestätigte Ziel-/Exitabsicht, ein redigierter Monatsbrief für alle aktiven Positionen und getrennte Bestätigung ausgeführter TRIM-/EXIT-Ereignisse. Eine Position benötigt keinen vorherigen Scanner- oder Radarfall. Eine Empfehlung handelt nicht.

Der einfache Gesamtweg bleibt: Idee finden oder direkt nennen → prüfen → aussortieren, einen echten Beleg abwarten oder fertigen Vorschlag vorlegen → Owner entscheidet über Beobachtung/READY → erst ein tatsächlicher bestätigter Kauf erzeugt Bestand. Eine beendete Gelegenheit ist kein impliziter dauerhafter Ausschluss. Der Scanner kann eine wirklich spätere abgeschlossene Signalepisode erneut vorschlagen: gleicher/früherer bekannter Signalmonat bleibt gesperrt; das Ende des neuen Signalmonats muss nach dem dokumentierten Archivdatum liegen. Ohne ausreichende Archivprovenienz keine automatische Wiederaufnahme. Dieselbe Grenze gilt bei der bestätigten Candidate-Aufnahme, damit ein alter offener Candidate sie nicht umgehen kann. Ein ausdrücklicher direkter Research-/Aufnahmeauftrag bleibt ohne erfundene Scanner-Episode möglich. Dauerhafter Ausschluss bleibt eine getrennte menschliche Entscheidung.

Symbolbasierte Befehle wählen den laufenden, andernfalls den neuesten historischen Fall. `list` zeigt alle Case-IDs; `evaluate --case-id ID` adressiert eine historische Timingauswertung ausdrücklich. Bestehende Positionsverknüpfungen werden nicht auf einen neuen Fall desselben Symbols umgebogen. Die beiden betroffenen Tabellen werden beim vorhandenen `init` verlustfrei und idempotent auf die historische Mehrfachablage migriert; vor produktiver Migration wird ein SQLite-Backup geprüft.

Die produktiven Lanes verarbeiten das aktuelle US-Aktienuniversum wöchentlich aus dem lokalen historischen Drive-Korpus plus `AmirTrader/YahooFinance`; STOXX Europe 600 und kuratierte ETFs werden getrennt aus dem lokalen `yfinance`-Cache verarbeitet.
