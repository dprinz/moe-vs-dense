Gemessen am 2026-08-18 17:59:03 UTC, 1 Durchläufe je Modell, 8 Dokumente.

## Modelle

| | qwen3.6:35b-a3b | qwen3:8b | qwen3.8:27b | qwen3.6:27b |
| --- | --- | --- | --- | --- |
| Parameter | 36.0B | 8.2B | 27.3B | 27.8B |
| Quantisierung | Q4_K_M | Q4_K_M | Q4_K_M | Q4_K_M |
| Familie | qwen35moe | qwen3 | qwen35 | qwen35 |

## Genauigkeit

| Metrik | qwen3.6:35b-a3b | qwen3:8b | qwen3.8:27b | qwen3.6:27b |
| --- | --- | --- | --- | --- |
| OCR-Check richtig | 100 % | 100 % | 100 % | 100 % |
| Zeichenfehlerrate echte Handschrift | 23.7 % | — | 41.4 % | 36.5 % |
| Wortfehlerrate echte Handschrift | 40.9 % | — | 63.0 % | 55.7 % |
| Zeichenfehlerrate Handschrift-Font | 0.0 % | — | 0.0 % | 0.0 % |
| Wortfehlerrate Handschrift-Font | 0.0 % | — | 0.0 % | 0.0 % |
| Korrespondent richtig | 88 % | 100 % | 88 % | 88 % |
| Dokumenttyp richtig | 88 % | 75 % | 88 % | 75 % |
| Tags F1 | 0.81 | 0.92 | 0.89 | 0.88 |
| Datum richtig | 100 % | 100 % | 100 % | 100 % |
| Titel F1 | 0.56 | 0.38 | 0.41 | 0.43 |

## Geschwindigkeit

| | qwen3.6:35b-a3b | qwen3:8b | qwen3.8:27b | qwen3.6:27b |
| --- | --- | --- | --- | --- |
| Sekunden je Dokument | 81 s | 32 s | 99 s | 388 s |
| OCR-Check Tokens/s | 68.8 | 47.3 | 19.3 | 13.9 |
| Vision-OCR Tokens/s | 66.6 | — | 16.4 | 13.8 |
| Klassifikation Tokens/s | 68.2 | 47.1 | 21.3 | 13.9 |
| Metadaten Tokens/s | 68.5 | 47.5 | 21.4 | 13.9 |
| OCR-Check Dauer | 21 s | 9 s | 30 s | 103 s |
| Vision-OCR Dauer | 31 s | — | 26 s | 76 s |
| Klassifikation Dauer | 24 s | 11 s | 27 s | 113 s |
| Metadaten Dauer | 21 s | 12 s | 29 s | 134 s |
