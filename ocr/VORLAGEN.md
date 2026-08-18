# Schreibvorlage

Je ein Dokument auf ein A4-Blatt, von Hand, in normaler Alltagsschrift.

## Ablauf

1. Nicht besonders sauber schreiben — gemessen werden soll der Alltagsfall,
   nicht die Sonntagsschrift.
2. Zeilenumbrüche ungefähr wie unten. Auf die Zeichenfehlerrate wirkt sich das
   nicht aus, Whitespace wird vor dem Vergleich zusammengezogen.
3. Blatt scannen, als PDF, 150 dpi oder mehr.
4. Ablegen unter dem Namen, der in der Überschrift steht.

Danach `python -m bench.corpus` ausführen. Wo ein PDF liegt, kommt das Dokument
als echte Handschrift in den Korpus; wo keines liegt, wird der Text mit einem
Handschrift-Font gerendert und in der Auswertung getrennt ausgewiesen. Der
Korpus ist also jederzeit lauffähig.

`d05` und `d06` sind geschrieben. `d07` und `d08` werden es nicht — sie bleiben
Font und dienen als Gegenprobe: ein Modell, das den Font fehlerfrei liest und
an echter Handschrift scheitert, zeigt genau den Unterschied, um den es geht.
Die Vorlagen bleiben stehen, weil sie den Inhalt der Font-Dokumente
dokumentieren und den Weg offenhalten, ein weiteres Blatt hinzuzunehmen.

## Korrekturen sind erwünscht

Durchgestrichene Stellen, krumme Zeilen und Verschreiber gehören dazu — genau
daran unterscheiden sich die Modelle. Der Referenztext ist und bleibt der unten
stehende: eine durchgestrichene Stelle soll das Modell gerade *nicht* lesen.

Weicht das Geschriebene inhaltlich von der Vorlage ab, muss die zugehörige
`.txt` nachgezogen werden. Sonst wird gegen eine Vorlage gemessen, die so nie
auf dem Papier stand.

---


## d05-hand.pdf — Kontaktliste Blockflötengruppe Mittwoch

*13 Zeilen, 49 Wörter — geschrieben*

Korrespondent: Musikschule Talgrund · Typ: Kontaktliste · Tags: bildung, freizeit · Datum: 2026-08-12

```text
Musikschule Talgrund
Kontaktliste Blockflötengruppe Mittwoch
Stand 12.8.2026

Gruppe A - Anfänger
Aaron A.
Tel 077 400 11 22, ab 17 Uhr

Abdul Al-Hazred
Tel 076 236 12 31, immer

Gruppe B - Fortgeschritten
Sol Weintraub
Tel 079 123 55 66, nachmittags

Johnny Rico
Tel 076 623 71 12, morgens
```


## d06-hand.pdf — Mahnung überfällige Medien

*8 Zeilen, 28 Wörter — geschrieben*

Korrespondent: Bibliothek Seefeld · Typ: Mahnung · Tags: freizeit, finanzen · Datum: 2026-06-30

```text
Bibliothek Seefeld
Mahnung überfällige Medien
Datum 30.06.2026

Ausweisnummer 4471
Drei Medien sind überfällig seit 12.06.2026
Mahngebühr 6.00 CHF
Zuschlag pro Woche 2.00 CHF
Bitte innert zehn Tagen zurückbringen
```


## d07-hand.pdf — Verlaufsnotiz Kontrolluntersuchung

*9 Zeilen, 28 Wörter — **wird nicht geschrieben**, bleibt Handschrift-Font*

Korrespondent: Kantonsspital Nordheim · Typ: Arztbericht · Tags: gesundheit · Datum: 2026-07-22

```text
Kantonsspital Nordheim
Ambulanz Innere Medizin
Verlaufsnotiz Kontrolluntersuchung
Datum 22.07.2026

Blutdruck 128 zu 82, Puls 68 regelmässig
Laborwerte unauffällig
Cholesterin leicht erhöht
Beurteilung: Verlauf zufriedenstellend
Kontrolle in sechs Monaten
```


## d08-hand.pdf — Anmeldeformular Neupatient

*9 Zeilen, 28 Wörter — **wird nicht geschrieben**, bleibt Handschrift-Font*

Korrespondent: Zahnarztpraxis Dr. Lehner · Typ: Anmeldeformular · Tags: gesundheit · Datum: 2026-08-03

```text
Zahnarztpraxis Dr. Lehner
Anmeldeformular Neupatient
Eingang: 03.08.2026

Versicherung: Grundversicherung
Letzte Kontrolle: vor zwei Jahren
Beschwerden: Empfindlichkeit oben rechts
Seit wann: etwa drei Wochen
Allergien: Penicillin
Gewünschter Termin: vormittags
```
