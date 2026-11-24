> Lokale, neutralisierte Vorlage. Kein aktiver Job, kein LLM-Aufruf, keine Versandfreigabe.

# Monatlicher Stockpicker-Positionsbrief

Arbeite im Repository `.` auf Deutsch.

## Ziel

Erstelle einmal pro Kalendermonat **einen redigierten Portfolio-Brief per E-Mail**.
Das ist kein Trading-Report. Es gibt keine täglichen oder wöchentlichen Zwischenmeldungen.

Arbeite mit belegten Primärquellen, getrennten Fakten/Annahmen und verständlicher Redaktion. Keine externen Agent-Skills werden mitgeliefert.

## 1. Vollständigkeit

Bestimme den aktuellen Monat als `YYYY-MM` und führe aus:

```bash
PYTHONPATH=src .venv/bin/python -m opportunity_radar.cli monthly-position-review-status \
  --db state/opportunity_radar.sqlite3 --period YYYY-MM
```

Prüfe jede Position in `missing_symbols` genau einmal. Nutze `show-position`,
die gespeicherte Baseline und aktuelle öffentliche Primärquellen. Bei ETFs
haben Emittenten-Factsheet, Indexunterlagen und aktuelle Holdings Vorrang.

Speichere je Position den Quellenbericht unter
`output/position-reviews/YYYY-MM-DD-SYMBOL.md` und anschließend genau eine
Empfehlung mit `record-position-review`: `HOLD`, `TRIM`, `EXIT` oder
`NO_DECISION`. Eine Empfehlung verändert niemals Menge oder Status. Führe nie
`confirm-position-event` aus.

Lies die tatsächlich gültige Baselineversion und binde im Review die konkrete `position_id` und `baseline_id` aus `show-position`. Eine Monatskorrektur benötigt `supersedes_review_id` und `correction_reason`, keine neue zufällige Tageskopie. Bei Chancenpositionen begründe, was vom ursprünglichen Pfad schon eingetreten ist und welche Aktionärsrendite ab heute über die verbleibende Zeit gegen SPY in EUR plausibel bleibt. Heutigen kompatiblen Preis, Cash-/FXannahmen, Schaden und Verzögerung offenlegen. Thesenintaktheit allein ist kein HOLD-Grund; verbrauchte Asymmetrie verlangt TRIM-/EXIT-Abwägung, keinen Trade. Core-/Hedgebestände nach bestätigter Funktion prüfen, nicht rückwirkend zu Chancenwetten machen. Ursprünglicher Endpunkt bleibt; Verlängerung nur als von Owner bestätigter Baseline-Nachfolger. Monatskorrekturen referenzieren ihren vorherigen Review ausdrücklich. NO_DECISION benennt echte Lücke und einen zukünftigen Prüfpunkt; fehlende Evidenz ist keine positive Haltebestätigung.

## 2. Redigierter Monatsbrief

Wenn und nur wenn der Status danach `complete: true` ist, lies alle Berichte des Monats. Erzeuge mit `monthly-position-review-context --db state/opportunity_radar.sqlite3 --period YYYY-MM` die aktuelle vollständige Entscheidungsbasis: Positionsepisoden, Baselineversionen, Reviews und gelesene Berichtsbytes. Eine seit dem Review geänderte Baseline verlangt einen passenden Nachfolgerreview, keine automatische Neubescheinigung alter Prosa. Redigiere daraus den Brief unter:

```text
output/position-reviews/YYYY-MM-portfolio-brief.md
```

Der Brief ist ein zusammenhängendes Leserprodukt, keine Verkettung von sechs
Einzelreports. Verwende diese Dramaturgie:

1. `# Stockpicker — Monatsbrief MMMM YYYY`
2. **Was diesen Monat zählt** — zwei bis vier Absätze mit dem Gesamtbild und
   der wichtigsten Gegenkraft.
3. **Handlungsbedarf** — zuerst; bei ausschließlich HOLD klar
   `Kein unmittelbarer Handlungsbedarf.` schreiben. TRIM/EXIT deutlich als
   Empfehlung kennzeichnen: Bestand unverändert bis zu Owners Bestätigung.
4. **Das Portfolio im Zusammenhang** — die tatsächlich bestätigten Positionsfunktionen
   miteinander einordnen; keine künstliche Gesamtthese erfinden.
5. **Die Positionen** — je Position ein kurzer, verständlicher Abschnitt:
   Urteil, materielle Veränderung, stärkstes Gegenargument und was bis zum
   nächsten Monatsbrief beobachtet wird.
6. **Quellen und Vertiefung** — Links nach Position gruppiert am Ende.

Schreibe flüssig und konkret. Keine internen Statuscodes im Lesetext, keine
Pipeline-Begriffe, keine Rohdatenwand, keine sechs identischen Mini-Templates,
keine Kursbewegung als These. Zahlen nur, wenn sie die Entscheidung erklären.

## 3. E-Mail

Schreibe nach abgeschlossener Redaktion `output/position-reviews/YYYY-MM-manifest.json` mit `period`, `context_digest` aus dem tatsächlich für den Brief gelesenen Kontext und `body_sha256` der finalen UTF-8-Briefbytes. Hash nicht erst im Versandweg automatisch neu erzeugen. Veränderte Inputs verlangen inhaltliche Wiederprüfung, nicht bloß einen neuen Hash. Fehlende/geleerte Quellenberichte verhindern die Vorbereitung; Inhaltsbindung ist kein MIME-Zustellungsbeweis.

Der Export bereitet ausschließlich lokale Artefakte vor. Nicht senden. Die optionalen Liveadapter benötigen separate Konfiguration und Autorisierung; siehe README.md.
