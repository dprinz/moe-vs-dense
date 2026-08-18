Gemessen am 2026-08-18 22:13:40 UTC, 3 Durchläufe je Modell, 8 Dokumente.

Rechner: Apple M5 Pro, 48 GB, ollama version is 0.32.14. Ollama vor jedem Modell neu gestartet.

## Modelle

| | qwen3.6:35b-a3b | qwen3.6:27b | qwen3.8:27b | qwen3:8b |
| --- | --- | --- | --- | --- |
| Parameter | 36.0B | 27.8B | 27.3B | 8.2B |
| Quantisierung | Q4_K_M | Q4_K_M | Q4_K_M | Q4_K_M |
| Familie | qwen35moe | qwen35 | qwen35 | qwen3 |

## Genauigkeit

| Metrik | qwen3.6:35b-a3b | qwen3.6:27b | qwen3.8:27b | qwen3:8b |
| --- | --- | --- | --- | --- |
| OCR-Check richtig | 96 % | 100 % | 100 % | 100 % |
| Zeichenfehlerrate echte Handschrift | 23.5 % | 34.0 % | 22.4 % | — |
| Wortfehlerrate echte Handschrift | 41.1 % | 56.5 % | 41.1 % | — |
| Zeichenfehlerrate Handschrift-Font | 0.0 % | 0.0 % | 0.0 % | — |
| Wortfehlerrate Handschrift-Font | 0.0 % | 0.0 % | 0.0 % | — |
| Korrespondent richtig | 88 % | 88 % | 88 % | 100 % |
| Dokumenttyp richtig | 79 % | 75 % | 88 % | 75 % |
| Tags F1 | 0.88 | 0.83 | 0.87 | 0.76 |
| Datum richtig | 100 % | 100 % | 100 % | 100 % |
| Titel F1 | 0.53 | 0.38 | 0.43 | 0.36 |

## Genauigkeit, nur gedruckte Dokumente

Die Teilmenge, die jedes Modell bearbeitet — auch eines ohne Vision. 12 Dokumentläufe je Modell.

| Metrik | qwen3.6:35b-a3b | qwen3.6:27b | qwen3.8:27b | qwen3:8b |
| --- | --- | --- | --- | --- |
| OCR-Check richtig | 100 % | 100 % | 100 % | 100 % |
| Korrespondent richtig | 100 % | 100 % | 100 % | 100 % |
| Dokumenttyp richtig | 75 % | 75 % | 75 % | 75 % |
| Tags F1 | 0.86 | 0.82 | 0.95 | 0.76 |
| Datum richtig | 100 % | 100 % | 100 % | 100 % |
| Titel F1 | 0.55 | 0.44 | 0.43 | 0.36 |

## Geschwindigkeit

| | qwen3.6:35b-a3b | qwen3.6:27b | qwen3.8:27b | qwen3:8b |
| --- | --- | --- | --- | --- |
| Sekunden je Dokument | 85 s | 367 s | 96 s | 37 s |
| OCR-Check Tokens/s | 68.0 | 14.8 | 18.8 | 46.4 |
| Vision-OCR Tokens/s | 67.1 | 14.5 | 15.0 | — |
| Klassifikation Tokens/s | 67.7 | 14.7 | 20.6 | 45.8 |
| Metadaten Tokens/s | 68.0 | 14.7 | 20.5 | 46.4 |
| OCR-Check Dauer | 21 s | 96 s | 32 s | 9 s |
| Vision-OCR Dauer | 33 s | 64 s | 20 s | — |
| Klassifikation Dauer | 24 s | 113 s | 28 s | 15 s |
| Metadaten Dauer | 23 s | 126 s | 26 s | 14 s |

## Streuung über die Durchläufe

Spannweite der Mittelwerte je Durchlauf. Wo sie in der Grössenordnung des Modellunterschieds liegt, trägt der Vergleich nicht.

| Metrik | qwen3.6:35b-a3b | qwen3.6:27b | qwen3.8:27b | qwen3:8b |
| --- | --- | --- | --- | --- |
| OCR-Check richtig | 88 % – 100 % | konstant | konstant | konstant |
| Zeichenfehlerrate echte Handschrift | 22.5 % – 24.8 % | 32.6 % – 35.3 % | 20.1 % – 23.6 % | — |
| Wortfehlerrate echte Handschrift | 40.0 % – 42.4 % | 55.7 % – 57.2 % | 39.5 % – 43.4 % | — |
| Zeichenfehlerrate Handschrift-Font | konstant | konstant | konstant | — |
| Wortfehlerrate Handschrift-Font | konstant | konstant | konstant | — |
| Korrespondent richtig | konstant | konstant | konstant | konstant |
| Dokumenttyp richtig | 75 % – 88 % | konstant | konstant | konstant |
| Tags F1 | 0.85 – 0.90 | 0.79 – 0.88 | konstant | 0.71 – 0.83 |
| Datum richtig | konstant | konstant | konstant | konstant |
| Titel F1 | 0.49 – 0.55 | 0.35 – 0.42 | 0.42 – 0.44 | 0.35 – 0.38 |

## Zeichenfehlerrate je Dokument

| Dokument | Schrift | qwen3.6:35b-a3b | qwen3.6:27b | qwen3.8:27b | qwen3:8b |
| --- | --- | --- | --- | --- | --- |
| d05 | echt | 11.0 % (10.4–12.2) | 10.8 % (9.4–12.5) | 10.2 % (9.7–10.4) | — |
| d06 | echt | 35.9 % (34.1–39.2) | 57.1 % (55.8–58.1) | 34.7 % (30.4–36.9) | — |
| d07 | font | 0.0 % | 0.0 % | 0.0 % | — |
| d08 | font | 0.0 % | 0.0 % | 0.0 % | — |

## Sekunden je Dokument, Durchlauf für Durchlauf

| Durchlauf | qwen3.6:35b-a3b | qwen3.6:27b | qwen3.8:27b | qwen3:8b |
| --- | --- | --- | --- | --- |
| 1 | 99 s | 359 s | 97 s | 39 s |
| 2 | 76 s | 367 s | 93 s | 38 s |
| 3 | 80 s | 375 s | 98 s | 35 s |

## Zustand des Rechners

| | qwen3.6:35b-a3b | qwen3.6:27b | qwen3.8:27b | qwen3:8b |
| --- | --- | --- | --- | --- |
| Runner-Speicher zuletzt | 26.4 GB | 28.2 GB | 29.2 GB | 10.8 GB |
| freier Speicher, Minimum | 5.7 GB | 8.6 GB | 9.7 GB | 22.2 GB |
| Swap, Maximum | 912 MB | 824 MB | 824 MB | 824 MB |
| thermisch gedrosselt | nein | nein | nein | nein |

## Alter der Ollama-Session

| | qwen3.6:35b-a3b | qwen3.6:27b | qwen3.8:27b | qwen3:8b |
| --- | --- | --- | --- | --- |
| bei Messbeginn | 0 min | 0 min | 0 min | 0 min |
| am Ende | 34 min | 147 min | 39 min | 8 min |
