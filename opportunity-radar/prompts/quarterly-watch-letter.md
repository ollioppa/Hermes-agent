> Lokale, neutralisierte Vorlage. Kein aktiver Job, kein LLM-Aufruf, keine Versandfreigabe.

# Vierteljährlicher WATCH-Brief

Arbeite im Repository `.` auf Deutsch.

## Zweck

Erstelle einmal pro Quartal **einen eigenständigen WATCH-Brief per E-Mail**.
Das ist weder ein Portfolio-Review noch ein erneuter vollständiger Stockpicker-
oder Deep-Dive-Lauf.

Arbeite mit belegten Primärquellen, getrennten Fakten/Annahmen und verständlicher Redaktion. Keine externen Agent-Skills werden mitgeliefert.

## 1. Gebundener Arbeitsumfang

Bestimme das aktuelle Quartal als `YYYY-QN` und erzeuge den Kontext:

```bash
PYTHONPATH=src .venv/bin/python scripts/render_quarterly_watch_context.py \
  --db state/opportunity_radar.sqlite3 \
  --period YYYY-QN > output/quarterly-watch-context.json
```

Der Kontext ist vollständig zu behandeln:

- `watch_cases`: alle bereits von Owner bestätigten WATCH-Fälle;
- `ready_cases`: bereits aufgenommene READY-Fälle ohne bestätigt verknüpften ACTIVE-Bestand;
- `awaiting_candidates`: alle vollständig recherchierten offenen Kandidaten,
  deren abschließende Einordnung noch bei Owner liegt.

Rohe Scanner-Treffer, unfertiges Research, vertagte Episoden und das Archiv
gehören nicht in diesen Brief.

## 2. Bestehende WATCH-Fälle

Prüfe die gespeicherte offene Bedingung und den Falsifikator gegen neue Primärquellen. Prüfe außerdem begrenzt die verbleibende Chance: eigener Zukunftspfad noch plausibel, heutiger kompatibler Preis, ursprünglicher Endpunkt und Restdauer, verzögerte Wertrealisierung und verbleibender S&P-Vorsprung über dieselbe Dauer in EUR. Eine intakte alte These ist kein Beweis heutiger Attraktivität. Kein routinemäßiger neuer Deep Dive und keine künstliche weitere WATCH-Bedingung; wirtschaftlichen Neubewertungsbedarf als Empfehlung ausweisen, nicht automatisch Status ändern.

Ordne jeden Fall genau einem Ergebnis zu:

- `KEEP_WATCH`: Bedingung weiter offen; These nicht gebrochen.
- `CONDITION_MET`: gespeicherte Bedingung ist durch neue Evidenz erfüllt.
- `RECHECK_REQUIRED`: verbleibende Asymmetrie oder Zeit-/Preisannahme trägt nicht mehr; erneute Entscheidung empfehlen, keine automatische Mutation.
- `THESIS_BROKEN`: der gespeicherte Falsifikator ist materiell eingetreten.
- `NO_DECISION`: genau eine entscheidende neue Information fehlt.

Das Ergebnis ist nur eine Empfehlung. Verändere niemals einen Radar-Status.

## 3. Bereits aufgenommene READY-Fälle

Prüfe These, Falsifikator, heutigen kompatiblen Preis und verbleibende Asymmetrie gegenüber SPY in EUR. Zeige, was schon realisiert ist, was ab heute bleibt und wie viel Zeit bis zum ursprünglichen Endpunkt verbleibt; die Uhr startet nicht neu. Bei verbrauchter Chance erneute Entscheidung empfehlen, keine automatische Mutation. Begrenztes Delta statt zweitem vollständigem Deep Dive.
READY hat keine offene WATCH-Bedingung. Ordne jeden Fall genau einmal ein:

- `KEEP_READY`: Entscheidungsgrundlage samt belegter aktueller Preisgrundlage trägt weiter.
- `RECHECK_REQUIRED`: neue Evidenz verlangt erneute menschliche Prüfung.
- `THESIS_BROKEN`: der gespeicherte Falsifikator ist eingetreten.
- `NO_DECISION`: die derzeitige Entscheidungsgrundlage reicht nicht; fehlenden Beleg nennen.

`reference` ist der historische gebundene Referenzkurs, ausdrücklich mit Datum,
Währung und Provider — kein aktueller Kurs. Beschaffe eine aktuelle Preisgrundlage
nur für nachweislich dasselbe Wertpapier/dieselbe Notierung und Preiseinheit.
Insbesondere ersetzt ein Nasdaq-/USD-Stand unter `AD` nicht die `AD.AS`-/EUR-
Referenz. Ohne passenden aktuellen Beleg bleibt die Preisbeurteilung offen;
kein KEEP_READY allein aufgrund einer alten Preisannahme und keine Relativzahl
aus unpassenden Kursreihen. Dieses Briefprodukt repariert keinen Marktprovider.

`position_link: UNCONFIRMED` bedeutet nicht „sicher nicht gekauft“.
`active_positions` liefert den bestätigten Bestand und seine expliziten Case-Links.
Keinen Ticker-Join erraten, keine Verknüpfung erzeugen und keine Position anlegen.
Ein ausdrücklich verknüpfter ACTIVE-Bestand bleibt im Monatsprodukt; ungeklärten
Besitz bei der Entscheidung sichtbar machen. Alle Empfehlungen lassen Status,
Bestand und Alarmregeln unverändert.

## 4. Neue Kandidaten

Lies den gespeicherten vollständigen Bericht und seine Zeit-/Preisanker. Prüfe einen heutigen kompatiblen Preis auch ohne neue Veröffentlichung: Kursänderung kann die Chance verbrauchen oder verbessern. Aktualisiere entscheidungsrelevante Fundamentaldaten bei materieller neuer Evidenz, keine komplette Wiederholungsrecherche. Fehlende aktuelle Preisgrundlage nicht als Bestätigung ausgeben.

Ordne jeden Kandidaten genau einem Ergebnis zu:

- `WATCH_PROPOSAL`: wirtschaftlich grundsätzlich tragfähig und genau eine
  konkrete, überprüfbare Bedingung fehlt;
- `DECISION_READY`: vollständig entscheidungsreif; nicht künstlich durch WATCH
  schleusen;
- `NOT_WATCH`: mehrere notwendige Reparaturen, unzureichende These oder keine
  passende WATCH-Bedingung.

Eine Aufnahme in WATCH erfolgt ausschließlich nach Owners ausdrücklicher
Bestätigung. Der Agent darf weder einen Case anlegen noch einen Status ändern.

## 5. Redigierter Brief

Schreibe:

```text
output/watch-reviews/YYYY-QN-watch-brief.md
```

Der Brief führt den Leser in Alltagssprache:

1. `# Stockpicker — WATCH-Brief QN YYYY`
2. **Worum es dieses Quartal geht** — zwei bis vier Absätze: Was beobachten
   wir, warum ist es relevant, was bedeutet es praktisch?
3. **Bestehende WATCH-Fälle** — je Fall: offene Frage, neue Evidenz,
   Gegenargument und Empfehlung.
4. **Bereits aufgenommene READY-Fälle** — These, neue Evidenz, Preisgrundlage,
   Gegenargument und Empfehlung. Von noch nicht aufgenommenen Kandidaten trennen.
5. **Neue WATCH-Vorschläge** — nur `WATCH_PROPOSAL`, mit genau einer klaren
   Bedingung und einer expliziten Entscheidung für Owner.
6. **Neue entscheidungsreife Vorschläge** — nur `DECISION_READY`, klar getrennt von
   WATCH. Keine automatische Aufnahme oder Kaufempfehlung.
7. **Was Owner entscheiden muss** — kurze Liste; wenn nichts ansteht, klar
   sagen.
8. **Quellen und Vertiefung** — nach Fall gruppiert am Ende.

`NOT_WATCH`-Kandidaten werden nicht als Friedhof aufgelistet. Interne Codes,
Queue-Namen, Pipeline-Statistiken und operative Logs bleiben aus dem Lesetext.
Keine Kursbewegung allein gilt als fundamentale Evidenz.

## 6. Vollständigkeitsmanifest

Schreibe zusätzlich:

```text
output/watch-reviews/YYYY-QN-manifest.json
```

Exaktes Format:

```json
{
  "period": "YYYY-QN",
  "context_digest": "exakt aus output/quarterly-watch-context.json",
  "body_sha256": "SHA-256 der finalen UTF-8-Bytes des gelesenen Briefs",
  "watch_outcomes": [
    {"symbol": "SYMBOL", "outcome": "KEEP_WATCH|CONDITION_MET|RECHECK_REQUIRED|THESIS_BROKEN|NO_DECISION"}
  ],
  "ready_outcomes": [
    {"symbol": "SYMBOL", "outcome": "KEEP_READY|RECHECK_REQUIRED|THESIS_BROKEN|NO_DECISION"}
  ],
  "candidate_outcomes": [
    {"candidate_id": 123, "stable_identity": "IDENTITY", "signal_date": "YYYY-MM", "symbol": "SYMBOL", "outcome": "WATCH_PROPOSAL|DECISION_READY|NOT_WATCH"}
  ]
}
```

`context_digest` wird unverändert aus dem erzeugten Kontext übernommen.
Für Candidate-Ergebnisse auch `candidate_id`, `stable_identity` und `signal_date`
exakt aus `awaiting_candidates` übernehmen; gleiche Symbole dürfen verschiedene
Identitäten bezeichnen und müssen dann separat enthalten sein. Historische
Manifestdateien bleiben unverändert lesbar; sie werden nicht umgeschrieben,
neu gehasht oder erneut zugestellt. Neue Versandfreigaben benötigen diese Bindung.
Reihenfolge und Symbole entsprechen exakt diesem Kontext. Jeder Fall muss
genau einmal enthalten sein. Ändert sich zwischen Recherche und Versand ein
Review, eine offene Bedingung, Bestandszuordnung, gelesener Candidate-Bericht
oder eine Kandidatenepisode, verweigert der
Mailer den veralteten Brief.

Alle drei Ergebnislisten sind Pflicht; bei leerer Kontextgruppe `[]` verwenden.
Der Kontextdigest bindet auch `report_sha256` der gelesenen Candidate-Berichte; `body_sha256` bindet den finalen Brief. Hash erst nach abgeschlossener Redaktion berechnen, keine automatische Neuberechnung im Versandweg. Mailer liest Body einmal und versendet genau diese geprüften Bytes. Fehlende Berichte blockieren Vorbereitung; Hashbindung beweist keine Textqualität oder MIME-Inhaltsgleichheit.

## 7. E-Mail

Der Export bereitet ausschließlich lokale Artefakte vor. Nicht senden. Siehe README.md für Betriebsgrenzen.
