> Export-Vertragsreferenz, kein Nachweis aktiver Jobs oder produktiver Zustellung. Persönliche Betriebsbindungen wurden entfernt.

# Position Lifecycle Contract

> **Status:** Positionsakte, Review-Empfehlungen und bestätigte TRIM-/EXIT-Ereignisse sind produktiv. Der Positionsreview läuft einmal monatlich über alle aktiven Positionen und wird als ein redigierter Portfolio-Brief per E-Mail zugestellt.

## Zweck und Grenze

Ein Radar-`case` beschreibt eine mögliche Gelegenheit. Eine `position` beschreibt ein bewusst gehaltenes Wertpapier. Beide dürfen verknüpft sein, aber keiner ihrer Zustände wird aus dem anderen abgeleitet.

Die Positionsakte enthält ausschließlich bewusst bestätigte Wertpapierpositionen; sie ist kein Gesamtvermögensverzeichnis.

- Radar-Zustände: `INBOX`, `WATCH`, `READY`, `INVALIDATED`, `ARCHIVED`.
- Positionszustände: `ACTIVE`, `CLOSED`.
- Research verändert nie Menge oder Positionsstatus.
- Nur Owner darf eine Position importieren oder später einen ausgeführten Teil-/Vollverkauf bestätigen.

## Schlanke Positionsakte

Eine aktive Position speichert:

- Wertpapier, Art und Währung;
- optional den verknüpften Radar-Fall und einen Benchmark;
- Kaufdatum nur wenn bekannt; eine Näherung wird sichtbar markiert;
- Durchschnittspreis, Menge und Einsatz;
- Ziel der Position;
- Zeithorizont;
- eine verständliche Exit-Strategie;
- Datum und Herkunft der heute aufgestellten Prüfbasis.

Unbekannte historische Fakten werden nicht aus heutigen Berichten zurückerfunden. Für einen alten Bestand ist ein unbekanntes Kaufdatum zulässig. Die Prüfbasis sagt ausdrücklich, welche Werte aus dem Brokerexport und welche Strategieangaben von Owner stammen.

Detaillierte Thesis-, Bewertungs-, Zeit-, Portfolio-, Risiko-, Trim- und Vollverkaufsregeln werden nicht beim Import erzwungen. Ein späterer Positionsreview darf die Strategie präzisieren, aber keine angeblich historische Kaufthese erfinden.

## Bestätigung und Historie

`import-position --dry-run` validiert und zeigt die vollständige Prüfbasis, schreibt aber nichts. Nur `import-position --confirmed-by owner` erzeugt eine `ACTIVE` Position und Baseline-Version 1.

Die Baseline ist append-only. Sie kann weder aktualisiert noch gelöscht werden. `revise-position-baseline --confirmed-by owner` ergänzt eine begründete Nachfolgeversion mit `position_id`, aktuellem `predecessor_baseline_id`, `effective_on`, `change_reason` und ausschließlich Strategieänderungen in `baseline`. Kein Edit historischer Kaufdaten oder ausgeführter Bestandsmengen. Neue explizite opportunity-Baselines benötigen investment_frame mit ursprünglichem Bewertungsstart/Endpunkt, EUR-Vergleich und Reportpfad; Core/Hedge und unbekannte Altbestände dürfen ohne bleiben.

Es darf pro Symbol höchstens eine `ACTIVE` Position geben. Geschlossene historische Episoden dürfen später neben einer neuen Episode bestehen.

## Review und Ausführung

Ein Monatslauf prüft jede aktive Positionsepisode und ihre tatsächlich gelesene Baseline. Reviewpayload benötigt position_id und baseline_id; genau ein eindeutiger Blattreview pro Episode/Monat zählt. Korrekturen sind append-only Nachfolger mit supersedes_review_id und correction_reason, nicht zufällige Mehrfachreviews. Mehrdeutige oder historisch ungebundene Altmonate werden nicht automatisch bestätigt. Ein abgebrochener Lauf kann fehlende Positionen nachholen, versendet aber erst, wenn für alle aktiven Positionen ein Review des Monats gespeichert ist. Es gibt keine täglichen oder wöchentlichen Positionsmeldungen.

Ein Review speichert genau eine Empfehlung:

- `HOLD`
- `TRIM`
- `EXIT`
- `NO_DECISION`

Die Empfehlung enthält eine kurze Begründung, das stärkste Gegenargument und den Berichtspfad. `NO_DECISION` braucht genau eine fehlende Entscheidungsinformation und ein datiertes nächstes Prüfdatum; dieses Datum ist ein sichtbarer Hinweis, startet aber keinen täglichen Review-Job. Chancenpositionen benötigen ein positives Halteargument aus heutiger Restchance gegen SPY in EUR über den ursprünglichen Resthorizont; Thesenintaktheit allein genügt nicht. Verbrauchte Asymmetrie verlangt ausdrückliche TRIM/EXIT-Abwägung. Core/Hedge behalten ihre bestätigte Funktion. Ein späterer Kauf oder Review setzt den Endpunkt nicht zurück; Verlängerung erfordert bestätigte neue Prognose-/Baselineversion. Der Leser erhält nicht sechs aneinandergereihte Einzelberichte, sondern einen redigierten Monatsbrief mit Gesamtbild, Handlungsbedarf, Portfoliozusammenhang und kurzen Positionsabschnitten.

Ein Review verändert niemals Menge oder Status. Nur `confirm-position-event --confirmed-by owner` darf einen tatsächlich ausgeführten `TRIM` oder `EXIT` speichern. `TRIM` reduziert die Menge; `EXIT` schließt die Position. Beide bleiben append-only. Die Identität ist position_id plus execution_reference: identischer Retry liefert das ursprüngliche Event auch nach EXIT/neuer Episode, kollidierende Nutzlast wird abgewiesen. Bekannte Kauf-/Bestandssnapshot-/Ereignischronologie prüfen; mehrdeutig rück- oder gleichdatierte neue Events nicht still buchen. Unbekannte Daten bleiben unbekannt.

## Noch nicht produktiv

Die Positionsakte enthält ausdrücklich noch nicht:

- Nachkauf und Tax-Lot-Buchhaltung;
- automatische Orders;
- Brokerintegration;
- einen zusätzlichen Digest oder getrennte Weekly-/Monthly-Queues.

Eine Empfehlung handelt niemals selbst.
