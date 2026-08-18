# moe-vs-dense

Vergleicht ein Mixture-of-Experts-Modell mit einem dichten Modell auf genau der
Aufgabe, die eine produktive Dokumentenpipeline erledigt: handschriftliche
Scans per Vision-Modell lesen, dann Korrespondent, Dokumenttyp, Tags, Titel und
Datum extrahieren.

Der Anlass war eine konkrete Beobachtung: nach dem Wechsel auf ein dichtes
27B-Modell brauchte dieselbe Pipeline pro Dokument fünf bis zwölf Minuten und
lief teilweise in den Timeout. Die Vermutung, dass ein MoE mit weniger aktiven
Parametern deutlich schneller ist, liess sich nur mit Messung klären.

| | dense | MoE |
| --- | --- | --- |
| Modell | `qwen3.8:27b` | `qwen3.6:35b-a3b` |
| Parameter gesamt | 27B | 36B |
| davon aktiv je Token | 27B | 3B |

Das grössere Modell ist das mit den wenigeren aktiven Parametern. Genau darum
geht es.

## Was gemessen wird

Die vier Stufen der Pipeline, einzeln instrumentiert:

| Stufe | Aufgabe | Metrik |
| --- | --- | --- |
| 1 | Ist der vorhandene OCR-Text brauchbar? | Trefferquote binär |
| 2 | Seitenbild lesen (Vision-OCR) | Zeichen- und Wortfehlerrate |
| 3 | Korrespondent, Dokumenttyp, Tags | exakter Treffer, F1 bei Tags |
| 4 | Titel und inhaltliches Datum | Token-F1, exakter Treffer |

Dazu je Stufe Wanduhrzeit, generierte Tokens und Tokens pro Sekunde. Die
Token-Rate kommt aus `eval_count` und `eval_duration` der Ollama-API und ist
damit unabhängig von Prompt-Länge und Ladezeit.

Die Prompts sind unverändert die aus dem produktiven Windmill-Script
übernommenen (`bench/prompts.py`). Gemessen wird die reale Aufgabe, nicht eine
für den Vergleich zurechtgelegte.

## Der Korpus

Acht Dokumente, alle erfunden — damit der Volltext exakt bekannt ist (ohne
Referenz keine Fehlerrate) und damit keine personenbezogenen Daten im
Repository liegen. Die Schrift dagegen ist zur Hälfte echt:

- **Vier gedruckte** (`d01`–`d04`), im Code definiert und als PNG gerendert.
  Niemand schreibt eine gedruckte Rechnung von Hand ab.
- **Zwei von Hand geschriebene** (`d05`, `d06`), auf Papier geschrieben und
  eingescannt, ohne Textebene im PDF. Referenztext von Hand abgetippt und als
  `.txt` neben dem Scan abgelegt.
- **Zwei mit Handschrift-Font gerenderte** (`d07`, `d08`) — dieselbe Sorte
  Text, aber ohne Stift. Sie bleiben Font und sind die Gegenprobe, kein Ersatz
  für ein drittes und viertes geschriebenes Blatt.

Der Handschrift-Font ist deutlich leichter zu lesen als echte Handschrift: alle
vision-fähigen Modelle lesen ihn fehlerfrei, er trennt also nichts. Die
Auswertung weist Font und echte Handschrift deshalb getrennt aus, und
aussagekräftig sind allein die Zahlen der zwei echten Blätter — womit die
Handschrift-Aussage auf zwei Dokumenten steht und entsprechend wenig trägt.
Ein weiteres Blatt kommt hinzu, indem PDF und abgetippter Referenztext gleichen
Namens unter `ocr/` abgelegt werden.

## Benutzung

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python -m bench.corpus                      # Seitenbilder erzeugen
.venv/bin/python -m bench.run \
    --base-url http://<ollama-host>:11434 \
    --models qwen3.6:27b qwen3.6:35b-a3b \
    --repeats 3 --restart-between-models
```

Ergebnisse landen als JSON in `results/`, die jeweils letzte zusätzlich als
`results/latest.json`. `bench/report.py` erzeugt daraus eine Markdown-Tabelle.

Einzelne Dokumente messen: `--only d01 s01`.

`--restart-between-models` gibt jedem Modell eine frische Ollama-Session. Ohne
das misst der spätere Teil eines Laufs eine Instanz mit Stunden Laufzeit, und
langsame Modelle stehen naturgemäss weiter hinten — der Messfehler sieht dann
aus wie ein Modellunterschied. Auf einem entfernten Server nimmt
`--restart-cmd "ssh <host> systemctl restart ollama"` die Stelle des lokalen
Neustarts ein.

Weil einzelne Durchläufe stark streuen, weist die Auswertung neben dem
Mittelwert die Spannweite über die Wiederholungen aus, dazu die Werte je
Dokument. Ein Genauigkeitsunterschied, der kleiner ist als die Streuung
desselben Modells, ist keiner.

## Aufbau

```
bench/corpus.py    Dokumente, Ground Truth, Rendering, OCR-Simulation
bench/prompts.py   die Prompts aus dem Windmill-Script
bench/ollama.py    HTTP-Client mit Zeitmessung
bench/metrics.py   CER, WER, F1, exakte Treffer
bench/session.py   Neustart der Ollama-Session zwischen den Modellen
bench/telemetry.py Zustand des Messrechners je Dokument
bench/run.py       Ablauf und Zusammenfassung
bench/report.py    Markdown-Bericht aus results/latest.json
ocr/               echte Scans: <name>.pdf plus <name>.txt als Referenz
```

Ein weiterer Scan wird eingebunden, indem PDF und abgetippter Referenztext
gleichen Namens unter `ocr/` abgelegt werden.

## Einschränkungen

Ein Rechner, acht Dokumente, drei Durchläufe je Konfiguration. Das reicht, um
einen Grössenordnungsunterschied bei der Geschwindigkeit zu belegen, nicht um
kleine Genauigkeitsunterschiede statistisch abzusichern — dafür streut dasselbe
Modell auf demselben Bild zu stark. Beide Modelle laufen quantisiert; die
Quantisierung ist Teil des Vergleichs und nicht herausgerechnet.

Ergebnisse verschiedener Läufe sind nur innerhalb eines Laufs vergleichbar. Der
Rechner steht deshalb im Ergebnis-JSON, und je Dokument werden Speicher, Swap
und thermische Drosselung mitgeschrieben: ohne diese Daten neben den Zeiten
lässt sich hinterher nicht entscheiden, ob ein Modell langsam war oder der
Rechner.
