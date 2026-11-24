> Export-Vertragsreferenz, kein Nachweis aktiver Jobs oder produktiver Zustellung. Persönliche Betriebsbindungen wurden entfernt.

# Watchdog- und Mailvertrag v0.1

## Betriebsfluss

### Eventlauf

Werktags 22:45 Europe/Berlin:

1. Für `WATCH`-/`READY`-Cases wird ein stichtagsgleicher gebundener Satz aus Case, SPY und Sektor gespeichert, gemäß ursprünglichem Instrument/Provider; kein stiller Nasdaq-Ersatz einer EUR-Notierung.
2. Der Watchdog prüft ausschließlich Beobachtungsdauer, Relativbewegung, optionale Preisgrenze, Quellenalter und Datenfrische.
3. Der erste Lauf setzt eine stille Baseline.
4. Nur ein Boolean-Wechsel erzeugt ein append-only Event.
5. Neue, noch nicht quittierte Events werden als eine kurze Mail versendet.
6. Der Watchdog ändert niemals den Investmentstatus.

### Quartalsbrief

Am 15. Februar, Mai, August und November um 09:30 Europe/Berlin wird höchstens eine Mail pro Quartal versendet. Sie enthält:

- bestehende `WATCH`-Fälle gegen gespeicherte Bedingung/Falsifikator und begrenzt gegen heutige Preis-, Restdauer- und Chancenannahme geprüft;
- bereits aufgenommene `READY`-Fälle, getrennt gegen gespeicherte These, Falsifikator und Preisannahme geprüft; keine erfundene WATCH-Bedingung;
- fertig recherchierte, an ihre aktuelle Signalepisode gebundene Kandidaten, getrennt als WATCH-Vorschlag, direkt entscheidungsreif oder nicht leserrelevant;
- eine klare Rubrik für Entscheidungen, die Owner tatsächlich treffen muss.

Der Quartalsbrief startet keinen neuen Deep Dive, zeigt keine DROP-/DEFER-Inventare und nimmt niemanden automatisch in `WATCH` oder `READY` auf. Explizit mit einem READY-Fall verknüpfter ACTIVE-Bestand gehört ins Monatsprodukt; ohne Link bleibt der Besitz unbestätigt, nicht automatisch ausgeschlossen. Ein vollständiges Manifest bindet den Brief an Reviewinhalt, Quellen, Zugehörigkeit/Bestandszuordnung und tatsächlich gelesene Candidate-Berichte. Veraltete oder unvollständige Entwürfe werden nicht versendet. `ready_outcomes` deckt jeden READY-Fall genau einmal als `KEEP_READY`, `RECHECK_REQUIRED`, `THESIS_BROKEN` oder `NO_DECISION` ab; dies sind Briefempfehlungen, keine neuen Radarzustände.

READY-Referenzen sind historische Preise mit Datum, Währung und Provider. Eine aktuelle Preisbeurteilung benötigt nachweislich dieselbe Notierung und Preiseinheit; insbesondere kein Nasdaq-/USD-Ersatz für AD.AS/EUR. Ohne passenden aktuellen Beleg bleibt die Preisbeurteilung offen, kein `KEEP_READY` allein aus der alten Referenz. Der bestehende Quote-/Readerfehler wird hierdurch nicht repariert.

## Delivery

Empfänger: `radar@example.invalid`.

- Deterministischer Delivery-Key und Subject pro Quartal.
- Vor dem Versand wird der Sent-Ordner nach exakt Subject + Empfänger geprüft.
- Nach SMTP wird die gespeicherte MIME-Nachricht exportiert und auf exakt `To:` + `Subject:` geprüft.
- Erst danach entsteht ein lokaler Receipt.
- Briefmanifeste verbinden den finalen Bodyhash mit den tatsächlich gelesenen Inputs; genau diese einmal gelesenen Bytes werden gesendet. Beim Monatsbrief gehören Positionsepisoden, Baselines, Reviewversionen und Berichtsbytes dazu.
- Receipt und Pending-Marker binden denselben Body. Identischer Wiederholungsaufruf sendet nicht erneut; abweichender oder historisch ungebundener Body verlangt explizite Klärung, kein automatischer neuer Versand und keine falsche Inhaltsbestätigung.
- Ein Sent-Headerfund allein beweist nicht die Bodygleichheit. Bestehende Quittungen bleiben historisch erhalten; keine zusätzliche MIME-Nachweisplattform.

## Authority

Der Event-Watchdog meldet nur definierte Signalwechsel. Der Quartalsbrief gibt Empfehlungen und Entscheidungsvorlagen. Beide setzen niemals `WATCH` oder `READY`; diese Zustände bleiben explizite Entscheidungen Owners.

## Fehlerverhalten

- Keine Änderung: Eventscript stdout bleibt leer.
- Provider-, DB- oder Mailfehler: Prozess endet ungleich null; kein falscher Receipt.
- Fundamentale Aussagen werden nicht aus Kursdaten abgeleitet.
- Eingehende Mailantworten werden nicht verarbeitet.
