> Export-Vertragsreferenz, kein Nachweis aktiver Jobs oder produktiver Zustellung. Persönliche Betriebsbindungen wurden entfernt.

# Evaluation — Preisbeobachtung und Evidenzgrenzen

## Zwei getrennte Fragen

- **Selektion:** Welche Ideen entwickeln sich nach dem eingefrorenen Erstreview relativ zu SPY und einer naheliegenden Sektoralternative? Aktien/ETFs, positive/negative Entscheidungen und Beobachtungsdauern getrennt halten. Nur aktive Gewinner zu verfolgen erzeugt Selektionsbias; ungeprüfte oder fehlende Nachbeobachtung bleibt sichtbar, keine Erfolgsquote daraus.
- **Timing:** Welcher relative Preisweg lag zwischen Schatteneinstieg und dem tatsächlich gebundenen READY-Endpunkt? Positiver relativer Anstieg ist beschreibende Confirmation Tax, negativer Verlauf beschreibt vermiedenen relativen Preisverlust; beides beweist keinen optimalen Kaufzeitpunkt.

Schatteneinstieg = ursprüngliche Idee; READY = Entscheidungsreife; Position = bestätigter tatsächlicher Besitz. Die Basen nicht gleichsetzen. Ein unbekanntes Kaufdatum oder fehlende Ausschüttungen bleiben unbekannt.

## Aktiver Datenpfad

`outcome-live` speichert einen append-only Case-/SPY-/Sektor-Satz samt Status. Jeder historische Case behält seinen eigenen Schatteneinstieg und Outcomes; ein neuer Case desselben Symbols setzt nichts zurück. `evaluate --case-id ID` adressiert den historischen Fall. Symbolbasierte Befehle wählen den laufenden, andernfalls neuesten historischen Fall.

Die vorhandene Marktbindung prüft Instrument/Symbol, Provider, Währung und Preissemantik. Aktuelle Anzeige verwendet den jüngsten passenden Satz einschließlich geeigneter Outcomes; historische Evaluation benötigt ihren gebundenen Endpunktsatz. Eine später eingefügte fremde Benchmark desselben Tags darf alte Ergebnisse nicht verändern. Unklar rekonstruierbare Altbindungen werden nicht erfunden. Preise müssen positiv und endlich, Daten kanonisch und Endpunkte chronologisch sein. Fehlende Beobachtung ist keine Nullrendite.

Rohvergleich, Startdatum und Beobachtungsdauer sind sichtbar. Mehrere Beobachtungen desselben Falls sind keine unabhängigen Treffer. Kleine oder unreife Stichproben bleiben deskriptiv. Archivierte/abgelehnte Gelegenheiten müssen für eine spätere vergleichbare Bewertung dieselbe Nachbeobachtungsdisziplin bekommen; die bestehende Abdeckung wird nicht als vollständig ausgegeben.

## Renditesemantik und bewusst ausgesetzte Aktivierung

Heutige Zahlen sind **lokale Preisrenditen ohne vollständige Dividenden- oder FXbereinigung**. Nasdaq-Last-Sale und die verwendeten Yahoo-Close-Spalten sind kein verifizierter Anleger-Gesamtertrag. Bestätigte lokale Watchdogschwellen behalten ihre Bedeutung.

Produktive Total-Return-/FXausgabe und deren Vollständigkeitsabnahme bleiben gemäß reviewed Scope ausgesetzt. Zulässig ist lesende Prüfung der vorhandenen Datenquellen und Dokumentation ihrer Abdeckung. Vor einer späteren Aktivierung müssen Ausschüttungen/Wiederanlage, Splits/Corporate Actions, ADR-/Aktieneinheiten, Datumsabgleich und EUR-Konversion auf beiden Seiten nachgewiesen sein. SPY ist ein investierbarer S&P-Proxy, nicht automatisch der exakte Indexgesamtertrag. Neue Kosten/Provider brauchen Freigabe. Keine langfristigen Performance- oder Alpha-Claims aus Preisbeobachtungen.

Davon unabhängig stehen **ex-ante Prognosen** im vollständigen Researchbericht: Aktie und SPY über denselben Zukunftshorizont in EUR, explizite FX-/Ausschüttungskonvention und plausible Indexszenarien. Diese Modellannahmen sind weder beobachtete Performance noch universelle feste Renditehürde.

## Nutzenprüfung ohne neue Runtime-Gates

Timing- oder Auswahlbehauptungen herabstufen, wenn ausreichend vergleichbar nachbeobachtete Fälle ihren behaupteten Vorteil nicht zeigen. Die früheren kleinen Kalibrierungsstichproben beweisen keine Liveperformance. Pflege vereinfachen, wenn sie mehr Prosa als Entscheidungen erzeugt. Dies sind Forschungs-/Produktentscheidungen, keine neuen automatischen Statusregeln oder zusätzlichen Evaluationsdienste.
