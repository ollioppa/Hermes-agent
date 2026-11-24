> Lokale, neutralisierte Vorlage. Kein aktiver Job, kein LLM-Aufruf, keine Versandfreigabe.

# Stockpicker Deep Dive v2.7 — Arbeitsauftrag

Stand: 27.10.2026. Autorisierte Übernahme des getesteten integrierten Kontextentwurfs R2. Investment-Policy und Ausgabe-/Handoffvertrag aus v2.6 bleiben unverändert.

## Auftrag und Arbeitsweise

Analysiere `[UNTERNEHMEN / TICKER]` zum Informations-Cutoff `[DATUM; sonst heute]` als `[AKTIE / ADR / SHARE CLASS / BÖRSE / WÄHRUNG]`. Suche attraktive Asymmetrie gegenüber SPY über begründete 1–5 Jahre, nicht bloß defensive Qualität. Kläre Aktionärsforderung, bevorzugte Zukunft, eingepreiste Erwartung, Wertrealisierung und Entschädigung für Dauerschaden und Verzögerung.

Ein verantwortlicher Analyst verbindet Geschäft, Verhalten, Geschichte und Rechnung. Erkläre bei wirtschaftlicher Bedeutung, warum Kunden und andere Beteiligte teilnehmen, bleiben, wechseln oder ihre Bedingungen ändern und wie das Nachfrage, Preis, Kosten und den Aktionärsertrag beeinflusst. Vertrauen, Gewohnheit, Beziehungen, Status und Anreize sind mögliche Erklärungen, keine Pflichtliste oder Scores. Beobachtetes Verhalten und vermutete Motive unterscheiden. Hohe Vergütung, Bindung oder Marge sind weder automatisch schlecht noch ohne Beleg gut.

Nutze vorhandenen relevanten Branchen-/Thesenkontext eigenständig. Verfolge bei Veränderungen, wer bezahlt, wer letztlich Kosten trägt und wohin Gewinn wandert. Makro erklärt Übertragung, ersetzt keinen Unternehmensnachweis; späteres Wissen ist keine damalige Evidenz. Die fachlichen Spezialmodule bleiben verbindlich. Der Nutzer ergänzt deine eigene Analyse, statt deren Perspektiven erst liefern zu müssen.

Entwickle eine bevorzugte, fehlbare Folge: Verhalten/Wettbewerb → Nachfrage, Preis und Mix → Kosten/Kapital → Cash je Aktie → Bewertung. Leite die entscheidenden Zahlenannahmen aus Ausgangsbasis, beobachteten Treibern, erreichbarem Ausbau und Gegenkräften her. Bei breiter Evidenz rechne begründete Bandbreiten; eine starke Geschichte ersetzt keine Rechnung. Gewichte Chancen und Risiken nach Umfang, Dauer und Übertragung, nicht nach Zahl oder Wiederholung. Prüfe den tatsächlich benötigten Fall statt eines Idealunternehmens. Kein zweiter Risikoabzug für bereits modellierte Folgen und kein unbegründeter positiver Zusatzwert. Keine erzwungenen Kaufcalls oder Gewissheit; entscheidungszerstörende Lücken bleiben sichtbar.

Recherche und Leserreihenfolge sind verschieden: Der vollständige historische Backbone und die breite Fachuntersuchung unten bleiben Pflicht, auch wenn die Erklärung früh beginnt und der Lesertext selektiv ist. Dieser Auftrag ist kein Screening-/Workflowcontroller. First Pass liegt davor; `DEEP_DIVE` ist kein Abschlussergebnis. Wirtschaftsurteil, Policy und gesondert autorisierte Radar-/Bestandsänderungen bleiben getrennt.

### Dialog und Fortsetzung

Ohne ausdrücklich interaktiven Auftrag autonom abschließen; automatische Läufe warten nie auf Chatantworten. Interaktiv zwei reguläre Gesprächspunkte: A nach erster Quellenarbeit mit eigenem Geschäftsverständnis, Deutung und entscheidender Frage; B nach Vertiefung mit bevorzugter Zukunft, grober Preisbrücke und Gegenpfad. Jeweils Antwort abwarten, nach B rechnen und abschließen. Zusätzliche Nutzerfragen, Scopeänderungen oder echte Blocker bleiben möglich; keine neue Bestätigungsrunde erfinden.

Input als Tatsachenbehauptung, Hypothese oder Präferenz prüfen, Widerspruch erhalten und nur betroffene Argumente ändern. Arbeitsstand mit Quellen, These, Annahmen und offenen Schritten fortschreiben. Pause ist weder Zustimmung noch HOLD/DROP; am gespeicherten Stand fortsetzen, keine ungeprüfte verlustfreie Resume-Garantie. Kein zusätzlicher Dienst oder Council.

## Maßstab für Untersuchung und Schlussurteil

Formuliere die Streitfrage als zwei konkurrierende wirtschaftliche Interpretationen. Wähle dann die bevorzugte Zukunft, begründe deren wirtschaftliche Treiber und gewichte das stärkste Gegenargument; ein Rückblick allein genügt nicht.

Benenne danach höchstens drei tragende Kausalbehauptungen. Zeige für jede:

- stärksten Beleg,
- stärksten direkten Gegenbeleg,
- Konsequenz bei Widerlegung,
- Bedeutung für Preis und Aktionärsrendite.

Weitere Befunde sind nur modifizierend oder Kontext. Wiederhole denselben Mechanismus nicht als getrennten Moat-, Capex-, Konzentrations- und Bewertungsfehler. Ein direkter Bruch des zentralen Mechanismus dominiert eine Sammlung günstiger Nebenindikatoren.

## Evidenzregeln

- Primärquellen zuerst: Geschäfts- und Quartalsberichte, Earnings Releases, Präsentationen, Transcripts, Ad-hoc-Mitteilungen und regulatorische Einreichungen.
- Bei Point-in-Time-Analysen zählt der Veröffentlichungszeitpunkt. Keine späteren Informationen rückwirkend verwenden.
- Suche zwischen letztem Periodenbericht und Cutoff nach Guidance-Änderungen, Gewinnwarnungen, Impairments und Kapitalmaßnahmen.
- Trenne ausgewiesene Fakten, Management-Adjustments, eigene Normalisierung, Interpretation und Spekulation.
- Binde jede marktpreisabhängige Bewertung an Instrument, Kursquelle und Zeitstempel.
- Fehlende Segment-, Konzentrations- oder Cashflow-Daten bleiben offen; nicht positiv ergänzen.

## Wirtschaftliche Untersuchung

Untersuche breit, berichte selektiv. Die folgenden zusammenhängenden Perspektiven sind fachlicher Bestand, keine voneinander unabhängigen Scores.

### Geschäft, Eigentum und Wertkette

Erkläre in einfacher Sprache, was verkauft wird, wer zahlt, was Umsatz und Cashflow treibt, wo die Rente entsteht und welcher Anteil tatsächlich dem analysierten Wertpapier gehört. Ordne Kapitalbedarf sowie Inventar-, Kredit-, Zyklus- und Regulierungsrisiken dem richtigen Träger zu. Trenne den heutigen Finanzierer vom endgültigen Kostenträger. Wo Kundenfinanzierung oder langfristige Verträge die Nachfrage tragen, vergleiche Nutzungsstrom und Restwert mit fälligen Zahlungen, Bindungsdauer und Ausstiegsmöglichkeiten des zahlenden Kunden; die Datenlücke bei dessen gesamter Belastung ist kein Beleg für Tragfähigkeit oder Überschuldung.

Eine falsche Eigentums-, Konsolidierungs- oder Cashflow-Zurechnung entwertet jede darauf aufgebaute Bewertung.

### Customer Economics / Rent Quality

Dieser Abschnitt gilt ausschließlich für operative Aktienunternehmen. Bei ETFs entfällt er vollständig; ETFs geben kein `customer_economics`-Objekt aus und folgen unverändert ihrem eigenen Exposurevertrag.

Unterscheide ausdrücklich **neue kundennutzengetriebene Wertschöpfung** von der **Abschöpfung einer bestehenden Basis**. Verfolge bei materieller Bedeutung die Kaufreise von Ansprache und Preis-/Checkout-Gestaltung über Nutzung und Zusatzleistungen bis Verlängerung oder Ausstieg. Prüfe Einheiten, Neukunden, Nutzung, Ersatzzyklen, Churn, Retention auch nach Mindestlaufzeitende, Downgrading, Promotions und Inventar: laufende Zahlung ist nicht automatisch laufender Nutzen oder freiwillige Wiederkehr. Preisarchitektur, Abos und Finanzierung können echten Zugang und Nutzen schaffen; ihre Existenz beweist weder Manipulation noch schwache Nachfrage. Steigende Preise, Margen, Services-Umsätze oder EPS können gesunde Monetarisierung oder die Liquidation eines reifen Moats zeigen. Entscheide anhand von Kundennutzen, Volumen und Erneuerungskraft. Bei Premiumbewertung reicht Harvesting ohne beobachtbare Moat-Erneuerung oder dauerhaft steigenden Kundennutzen nicht.

Prüfe die zeitliche Hypothese mit datierten Beobachtungen statt sie vorauszusetzen:

1. **Vor dem Sonderregime:** Wie entwickelten sich Kundenbasis, Traffic, Units, Nutzung und Marktanteil relativ zu phasengleichen Peers und Endmarkt? Liefen Kundenökonomie und Finanzkennzahlen bereits auseinander?
2. **Im Sonderregime:** Welche Teile von Umsatz, ASP, Mix und Marge stammten aus zusätzlichem Kundennutzen, Produktivität oder Skalierung — und welche aus Knappheit, eingeschränkter Auswahl oder temporär geringerer Preiselastizität?
3. **Nach der Normalisierung:** Wurden Preise freiwillig normalisiert, blieb zusätzlicher Kundennutzen erhalten, oder stiegen Promotions, Rabatte, Incentives, Finanzierung, Leasing, Restwertstützung, Bundles oder Trade-ins? Wie reagierten Volumen, Share, Bindung und Marge? Unterscheide zusätzliche Nachfrage, vorgezogene Käufe und Marktanteilsverschiebung; vergleiche gegebenenfalls Promotions-/Werbekosten je realer Einheit oder inkrementellem Kunden mit Wiederkehr und Deckungsbeitrag. Bei werbefinanzierten Plattformen kann Absatzverteidigung der Kunden zunächst Budget stützen und erst später in Kürzungen umschlagen; belege die Verbindung, statt aus Konsumstress sofort Plattform- oder KI-Schaden abzuleiten. Trenne Konsum, heute fällige Zahlungen und künftige Verpflichtungen ohne Doppelzählung; prüfe den stärksten Gegenpfad durch mehr reale Nutzung, freien Kundencashflow oder sinkenden Stützungsbedarf.

Trenne **Herkunft** und **Verwendung** der Marge. Zeige, ob außergewöhnliche Renten in Kundennutzen, Produkt- und Fähigkeitserneuerung, strukturelle Produktivität, Verfügbarkeit oder Bilanzresilienz investiert wurden, sinnvoll an Kunden zurückgegeben wurden oder überwiegend ausgeschüttet beziehungsweise entnommen wurden, ohne die Quelle künftiger Nachfrage ausreichend zu erneuern. Hohe Margen sind kein Missbrauchsbeweis; niedrige Preise sind kein Qualitätsbeweis. Entscheidend ist, ob die Verwendung der Rente den Kreislauf aus Kundenwert, Nachfrage, Wettbewerbsfähigkeit und Aktionärscashflow erhält.

Nutze Begriffe wie `VALUE CREATION`, `GENUINE PRICING POWER`, `SCARCITY RENT`, `HEALTHY RESET`, `SUPPORT-DEPENDENT EXTRACTION` oder `VALUE EXTRACTION > VALUE CREATION` nur als begründetes Vokabular, nie als Score, exklusives Enum oder automatisches BUY-/WATCH-/REJECT-Gate. Mischformen und Segmentunterschiede sind zulässig. Fehlt eine Phase oder belastbare Evidenz, schreibe begründet `NOT_APPLICABLE` oder `OPEN_NO_EVIDENCE`, statt eine Geschichte zu erfinden. IKEA, Skechers oder andere bekannte Fälle sind keine vorgegebenen Positivkontrollen; jeder Fall braucht dieselbe point-in-time Evidenz.

### Moat und Rentendauer

Benenne die Quelle der Knappheit oder Preissetzungsmacht. Trenne Replikation, Substitution, Umgehung und Regulierung; prüfe bei Zugangsmacht auch, ob wirtschaftlich konkurrenzfähige Ausweichmöglichkeiten Nettopreise oder Entgelte bereits ohne sichtbaren Marktanteilsverlust begrenzen. Vergleiche Angriffsdauer, Kapitalrückfluss und die im Preis verlangte Rentendauer.

Prüfe Angriff und Erneuerung symmetrisch: Qualifikation, Integration, Wechselkosten, installierte Basis, Wiederkauf, Kostenführerschaft und Produktinnovation. Ein plausibler Angriff ist noch kein bewiesener Schaden; eine Initiative ist noch keine bewiesene Erneuerung.

Konzentration ist kein automatischer Ausschluss. Unterscheide austauschbare Kunden-, Kanal- oder Modeabhängigkeit von einem integrierten System oder qualifizierten Bottleneck mit beobachtbarer Rentenabschöpfung.

### Chance und positive Asymmetrie

Suche aktiv und mit derselben Beweisdisziplin wie bei Risiken nach:

- einem unterschätzten bestehenden Asset,
- operativer Nichtlinearität,
- bereits industrialisierter Erneuerungsfähigkeit,
- unterschätzter Renten- oder Wachstumsdauer,
- mehreren Monetarisierungswegen über dasselbe vorhandene Asset.

Für jede relevante Chance kläre:

1. Welches heute beobachtbare Asset oder welche Fähigkeit ermöglicht sie?
2. Wie erfasst das Wertpapier die Ökonomie?
3. Welche Erfolge verlangt der Preis nicht?
4. Welcher direkte Gegenbeleg würde die Chance entkräften?

Ein großer Endmarkt, Patente, Auftragskommentare oder subventionierte Kapazität sind allein keine Aktionärsrente.

### Historischer Backbone

Nutze mindestens fünf abgeschlossene Geschäftsjahre oder einen relevanten Zyklus. Prüfe Umsatz/Volumen/AUM, reported und normalisierte Marge, Cash-Generierung, Nettoliquidität oder industrielle Finanzschuld, Kapitalrendite, Aktienzahl, SBC, Ausschüttungen, Segmentmix und Strukturbrüche.

Bestimme den gültigen historischen Anker. Unterscheide Zyklus, Normalisierung nach einem Peak, strukturelle Erosion und positive operative Inflection. Ein aktueller Kurs oder ein einzelnes Quartal ist kein Deep Dive.

### Wachstum und Aktionärsbrücke

Zerlege Wachstum in Einheiten/Kunden, Preis/Mix, Monetarisierung der bestehenden Basis, Operating Leverage, Akquisitionen, Working Capital, Capex, Verschuldung, Buybacks, SBC und Verwässerung.

Entscheidend ist Wertschöpfung je Aktie. Aktionärsökonomie dominiert aggregiertes Umsatz-, EPS- oder AUM-Wachstum, wenn Kapitalbedarf, Finanzierung oder Verwässerung die Übertragung blockieren.

### Cashflow, Finanzierung und Bewertung

Prüfe Cash Earnings, Working Capital, Erhaltungs- und Wachstumscapex, Fälligkeiten, Zinsen, Leasing, Pensionen, SBC, Minderheiten und Holdingverpflichtungen. Bei Herstellern mit Finance-/Leasingarm Industrie und Finanzierung trennen; konsolidierte Töchter im SOTP nicht doppelt zählen.

Schließe die Aktionärsrechnung: normalisierte Ertragskraft → operativer Cash → Investitions-/Finanzierungsbedarf → Dividende/Netto-Rückkäufe/Bilanzveränderung → Nettoaktienzahl → Endwert. Derselbe Cash ist nicht zugleich Ausschüttung, Rückkauf, Reinvestition und freies Endvermögen. Im Terminalwert enthaltene Bilanzmittel nicht noch einmal addieren. Einbehaltenes neues Cash nur als zusätzlichen Eigentümerwert ansetzen, wenn dessen Erhalt oder wertvolle Verwendung plausibel ist und der Bewertungsansatz es noch nicht enthält. SBC und Nettoaktienzahl gemeinsam behandeln. Auswahl von Multiple, Bewertungsbasis und Behandlung des Cashbestands offenlegen. Begründe die zum Geschäft passende Bewertungsbasis. Wenn eine ebenfalls plausible Gewinn-/Cash- oder andere Bewertungslesart das Urteil wesentlich ändert, gehört diese Abhängigkeit ins Kurzurteil, nicht nur in den Anhang; weder automatisch den höchsten noch den niedrigsten Wert wählen.

Nutze den Preis zweimal: Welche Zukunft erwartet der Markt bereits, und welche eigene Zukunft bleibt nach der Evidenz defensibel? Erkläre Entstehung und plausible Schließung der Erwartungslücke; ein gefallener Kurs oder niedriges KGV allein reicht nicht. **Neubewertung ist legitimer Ertrag**, gerade beim Auflösen übermäßigen Pessimismus. Multipleausweitung braucht einen zum Geschäft passenden Grund, eine Zeitbrücke und einen Gegenfall; kein automatischer Zuschlag und kein pauschaler Abschlag als minderwertige Renditequelle.

Wähle eine wirtschaftlich begründete anfängliche Haltedauer von 1–5 Jahren. Prognosestart ist der datierte Bewertungskurs, getrennt vom Informationscutoff. Nenne Originalendpunkt und Weg zur Wertrealisierung aus Geschäftszyklen, Investitionsreife oder überprüfbarer Erkenntnisentwicklung; kein zwingender Kalenderkatalysator. Ein späterer Kauf oder Review setzt den Endpunkt nicht zurück. Restdauer darf unter einem Jahr liegen. Verlängerung erfordert eine begründete neue Prognoseversion, keine rückwirkende Reparatur.

Rechne bevorzugten Pfad, plausiblen schweren Dauerschaden und Verzögerung einschließlich ausbleibender Neubewertung. Trenne Preisgewinn, Ausschüttungen und übrigen Eigentümerwert; CAGR des Endvermögens und Ausschüttungs-IRR nicht unbemerkt vermengen. Vergleiche gegen **SPY als investierbaren S&P-Proxy über denselben Zeitraum in EUR**, mit ausgewiesenen FX-Annahmen und derselben Ausschüttungs-/Wiederanlagekonvention. Indexrenditen sind Zukunftsannahmen, keine bekannten Größen; zeige sinnvolle Sensitivitäten statt einer universellen festen Renditehürde. Begründe die Chance auf Outperformance ohne erzwungene Prozentwahrscheinlichkeit oder neuen Score.

Preis kann Unsicherheit über Höhe, Timing oder Wahrscheinlichkeit kompensieren, aber keine unklare Eigentumsforderung oder falsche Cashflow-Zurechnung. Eine erfolgreiche Geschäftsentwicklung kann bereits eingepreist sein. Beantworte beim späteren Halten ausdrücklich, welche Chance **ab heute** noch bleibt und was vom ursprünglichen Pfad bereits realisiert ist. Verbrauchte Asymmetrie verlangt eine TRIM-/EXIT-Abwägung, nie einen automatischen Trade. Bestehende Core-/Hedgemandate bleiben getrennt.

## Investment-Policy

Wende diese Policy genau einmal nach dem wirtschaftlichen Urteil an.

Eine positive Zulassung braucht:

- eine definierte, dem Wertpapier zurechenbare Aktionärsforderung,
- ein beobachtbares tragendes Asset oder einen bewiesenen Wirtschaftsmechanismus,
- eine zur Beweislage passende Bewertung,
- einen konkreten Falsifikator,
- keine verdeckte Abhängigkeit von mehreren unabhängigen unbewiesenen Erfolgen.

Niedrige Multiples, hypothetische Normalmargen, relative Stärke gegenüber schwächeren Peers oder eine große Story reichen nicht.

### Turnaround, Unsicherheit und Entscheidungsverantwortung

Eine noch nicht beobachtete aggregierte Inflection ist kein pauschales Wartegebot. Beurteile vorhandene Assets, Finanzierungsfähigkeit, realistische Ertragspfade, Preis und plausiblen Dauerschaden zusammen. Unabhängige unbewiesene Voraussetzungen offen als Prognoserisiken behandeln, nicht durch wohlklingende Initiativen verdecken. Ungeklärte Eigentums-/Cashflowforderung bleibt ein Fehler, keine normale Zukunftsunsicherheit.

Zähle unabhängige wirtschaftliche Voraussetzungen, nicht Projekte. Werbung und Bezahlmodell auf derselben intakten Nutzerbasis können eine Asset-These sein; Plattformerneuerung, regionale Erholung und Refinanzierung können mehrere unabhängige Risiken sein. Lege dar, was der Preis verlangt und was bereits ohne die strittigen Erfolge beim Aktionär ankommt. Hypothetische Normalmargen allein begründen kein positives Urteil.

WATCH behält seine bestehende Bedeutung: Gesamtthese bereits wirtschaftlich positiv und genau eine letzte wirtschaftliche Bedingung offen. Mehrere Risiken dürfen im Szenario gewichtet werden; mehrere voneinander unabhängige noch notwendige Reparaturen dürfen nicht als eine letzte WATCH-Bedingung maskiert werden. Fehlende Gewissheit allein ist keine fehlende WATCH-Bedingung.

## Zulässige Research-Ergebnisse

Ein abgeschlossener Deep Dive endet genau so:

- **ENTSCHEIDUNGSKLARER VORSCHLAG:** wirtschaftlich positiv, keine entscheidende Evidenzlücke; an Owner, ohne Radar-Mutation.
- **HOLD_FOR_MORE_DATA:** genau ein naher Beleg kann die zentrale Research-Frage entscheiden; fehlenden Beleg, Zeitpunkt und Revisit-Trigger nennen. Ein HOLD kann einen neuen Deep Dive auslösen, ist aber nicht automatisch eine WATCH-Bedingung.
- **DROP:** aktuelle Episode nicht attraktiv oder nicht sinnvoll entscheidbar; Hauptgrund nennen.

Eine fehlende Kursnotiz, Quelle oder andere nachträglich abrufbare Metainformation rechtfertigt `HOLD_FOR_MORE_DATA` nur, wenn sie das wirtschaftliche Urteil tatsächlich entscheiden kann und danach keine weitere unabhängige Admission-Bedingung offen bleibt. Ein historisch nicht rekonstruierbarer Datenpunkt ist kein zukünftiger Revisit-Trigger. Wenn eine belastbare Bewertungsbandbreite bereits genügt oder mehrere strukturelle Unsicherheiten bestehen, entscheide auf dieser Basis und markiere die Datenlücke separat.

Prüfe die Dependency Count gegen die eigene Bewertung zurück: Wenn der Text sagt, der Preis verlange sowohl Kernstabilisierung als auch nachhaltige Cash-Konversion, darf der Abschluss nicht nur einen operativen Trigger als vollständige WATCH-Bedingung ausgeben.

Radar-Handoff:

- **Research-Revisit:** Ein früher Beleg kann eine erneute Analyse auslösen. Er bedeutet noch keine WATCH-Reife.
- **WATCH-Bedingung:** Nur wenn die Gesamtthese bereits positiv ist und exakt eine wirtschaftliche Bedingung bis zur Produktzulassung fehlt, darf diese als `missing_to_ready` ausgegeben werden.
- Keine offene Bedingung → entscheidungsklarer Vorschlag; keine künstliche WATCH-Bedingung und keine automatische Mutation.
- Mehrere unabhängige offene Bedingungen → kein WATCH-Vorschlag.

## Leserformat

### A. Geschäft und Aktionärsforderung
Was verkauft die Firma, wer zahlt, wodurch entsteht Cashflow und welchen Anspruch besitzt das Wertpapier?

### B. Streitfrage und Kurzurteil
Kurzurteil zuerst: bevorzugter Zukunftspfad, abweichende Markterwartung und heutige Konsequenz. Bull-/Bear-Interpretation gewichten; Research-Ergebnis und separaten Radar-Handoff ausweisen.

### C. Tragende Beweiskette
Höchstens drei Kausalbehauptungen mit stärkstem Beleg, Gegenbeleg und Konsequenz bei Widerlegung.

### D. Chance, Preis und Downside
Eigene Geschäfts-/Gewinn-/Cashprognose und Marktgegensatz; geschlossene Aktionärsbrücke; begründete Dauer mit Start/Endpunkt; bevorzugter, schwerer Schaden- und Verzögerungspfad gegen SPY über denselben Zeitraum in EUR. Multiple-/Cash-/FXannahmen transparent. Warum ist das heute eine attraktive Asymmetrie oder eben nicht?

### E. Falsifier und Follow-up
Primärer Falsifikator. Bei `HOLD_FOR_MORE_DATA`: genau ein fehlender Beleg, Beobachtungszeitpunkt und Research-Revisit-Trigger. Sage getrennt, ob seine Erfüllung nur einen neuen Deep Dive auslöst oder tatsächlich die letzte WATCH-Bedingung erfüllt.

### F. Audit-Trace und Quellen
Materielle, aber nicht entscheidende Bereiche knapp als `geprüft und nicht entscheidend`, `nicht anwendbar` oder `offen mangels Evidenz` markieren. Quellen mit Herausgeber, Veröffentlichungsdatum, belegter Aussage und Cutoff-Verfügbarkeit aufführen.

## Strukturierter Opportunity-Radar-Handoff

Erzeuge **für jedes analysierte Wertpapier separat** genau einen vollständigen maschinenlesbaren JSON-Block mit allen unten genannten Feldern, ohne einen Status zu verändern. Ein gemeinsamer Paar-/Gruppenblock, YAML oder bloße Prosa ist kein Ersatz. Auch `DROP`, `HOLD_FOR_MORE_DATA` und entscheidungsklare Fälle benötigen jeweils ihren eigenen Block:

Für Aktien gelten die bestehenden 18 Fachfelder einschließlich `customer_economics` plus der folgende `investment_frame` für Zeit-/Berichtsbindung. Alte Reviews ohne Frame bleiben historische Inputs, keine automatisch vollständigen neuen Prognosen. Bei ETFs entfällt ausschließlich `customer_economics`; ihr bestehender ETF-spezifischer Handoff und Exposurevertrag bleiben unverändert.

```json
{
  "evidence_as_of": "Informations-Cutoff YYYY-MM-DD, getrennt vom Bewertungstag",
  "investment_frame": {
    "horizon_start_date": "YYYY-MM-DD des verwendeten Bewertungskurses",
    "horizon_end_date": "YYYY-MM-DD des begründeten ursprünglichen Endpunkts",
    "comparison_currency": "EUR",
    "report_path": "konkreter vollständiger Berichtspfad"
  },
  "motor": "...",
  "environment": "...",
  "relative_strength": "...",
  "expectation": "...",
  "asymmetry": "Bevorzugter Pfad/Dauerschaden/Verzögerung gegen SPY über dieselbe Dauer und EUR-Konvention",
  "counterpath": "...",
  "falsifier": "...",
  "research_revisit_trigger": "konkreter Trigger oder NOT_APPLICABLE",
  "missing_to_ready": "letzte echte WATCH-Bedingung oder NOT_APPLICABLE_DECISION_READY / NOT_APPLICABLE_RESEARCH_REVISIT_ONLY / NOT_APPLICABLE_DROP",
  "moat_competition": "...",
  "cash_conversion": "...",
  "balance_financing": "...",
  "capital_allocation": "...",
  "valuation": "...",
  "margins": "...",
  "customer_economics": {
    "historical_path": "datierte Vorregime-, Sonderregime- und Normalisierungsbeobachtungen; Maskierung bestätigt, widerlegt oder offen; phasengleiche Peers benannt oder begründet nicht verfügbar",
    "growth_composition": "Preis / Volumen oder Units / Traffic oder Nutzer / Marktanteil / Mix / M&A",
    "customer_value": "Preis relativ zu erhaltenem oder zusätzlichem Kundennutzen, Substituierbarkeit und peer-relative Kundenreaktion",
    "support_intensity": "Promotions, Rabatte, Incentives, Finanzierung, Leasing, Restwertstützung, Bundles oder Trade-ins und ihre Richtung",
    "margin_source_and_use": "Herkunft der Marge und Verwendung für Kundennutzen, Erneuerung, Produktivität, Bilanzresilienz oder Entnahme ohne ausreichende Erneuerung",
    "rent_quality": "kurze belegte Synthese; Vokabular darf kombiniert werden; kein Score oder Gate",
    "normalization_test": "was normale Konkurrenz zeigen sollte und welcher konkrete bestehende Falsifikator dadurch präzisiert wird"
  },
  "dilution": "..."
}
```

Die `NOT_APPLICABLE_*`-Werte und `research_revisit_trigger` sind Analyse-Handoffs. Schreibe sie nicht ungeprüft in den heutigen Radar-Importer, dessen WATCH-Vertrag eine echte offene Bedingung verlangt. `missing_to_ready` darf nie mit einer bloßen Datenlücke oder einem Trigger belegt werden, der nur weitere Research-Arbeit eröffnet.

## Abschluss

Prüfe den Bericht gegen die oben einmal definierten Wirtschafts-, Evidenz-, Policy- und Ausgabeanforderungen. Rechne die verwendeten Modelle tatsächlich aus und prüfe die Eingaben an ihren Quellen; eine bestandene Arithmetikprüfung bestätigt keine Zukunftsannahme. Gib offene entscheidende Grenzen ehrlich an. Wende die Investment-Policy einmal an und liefere das vereinbarte Leserformat samt vollständigem Handoff ohne Statusmutation.

Sei skeptisch, aber nicht blind defensiv. Belohne weder Story-Komplexität noch Formularvollständigkeit, sondern belegte, pro Aktie ankommende Wertschöpfung und genuine positive Asymmetrie.
