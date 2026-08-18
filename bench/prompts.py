"""Die Prompts aus dem produktiven Windmill-Script.

Übernommen aus ``f/paperless/agent/analyze_document.py``. Der Benchmark soll
messen, was die Pipeline tatsächlich tut, nicht eine für den Vergleich
zurechtgelegte Aufgabe. Wer die Prompts dort aendert, muss sie hier nachziehen —
sonst misst der Benchmark einen Stand, den es nicht mehr gibt.

Einzige Abweichung: die Referenzlisten kommen aus :mod:`bench.corpus` statt aus
der paperless-API.
"""

from __future__ import annotations

MAX_OCR_CHECK_CHARS = 6000
MAX_CLASSIFY_CHARS = 24000
MAX_METADATA_CHARS = 12000


def build_ocr_prompt(text: str) -> str:
    return f"""Du bewertest die Qualität eines OCR-Textes aus einem eingescannten Dokument.

Beurteile, ob der Text inhaltlich brauchbar ist, d.h. ob man daraus Absender, Inhalt und Datum des Dokuments zuverlässig ableiten kann.

WICHTIG: Formulare mit gedruckten Feldlabels (Rechnungsformulare, Berichtsformulare etc.)
sind NICHT brauchbar, wenn die eigentlichen INHALTE handschriftlich eingetragen sind und
das OCR diese Einträge nicht erfassen konnte — die Labels allein tragen keine Information.

Als NICHT brauchbar gilt:
- Zeichensalat, stark fragmentierte Wörter, systematisch verstümmelte Umlaute
  (z.B. "IN&- MR \\ltand", "Vrwok us smusx", "0b1rach")
- handschriftliche Inhalte, die der OCR nicht erfassen konnte (erkennbar an wirren
  Zeichenfolgen dort, wo Namen/Beträge/Daten stehen müssten)
- fast leerer Text bei offensichtlich vorhandenem Inhalt (z.B. nur Kopfzeile)

Kleine Fehler (einzelne falsche Zeichen, Zeilenumbrüche, leichte Formatierungsartefakte) sind OK und kein Grund für "nicht brauchbar".

Antworte AUSSCHLIESSLICH mit JSON:
{{"ok": true|false, "reason": "kurze Begründung auf Deutsch"}}

OCR-TEXT:
{text[:MAX_OCR_CHECK_CHARS]}"""


def build_vision_prompt() -> str:
    return """Extrahiere den vollständigen Text dieser Dokumentseite.

Regeln:
- Gib den Text so wieder, wie er auf der Seite steht, in natürlicher Lesereihenfolge.
- Übernimm Überschriften, Absätze, Tabelleninhalte (als Textzeilen), Beträge und Daten.
- Keine Kommentare, keine Beschreibungen des Layouts, keine Zusammenfassung — NUR der extrahierte Text."""


def build_classify_prompt(
    text: str,
    correspondents: list[dict],
    document_types: list[dict],
    tags: list[dict],
) -> str:
    corr_list = "\n".join(f'  {{"id": {c["id"]}, "name": "{c["name"]}"}}' for c in correspondents) or "  (leer)"
    type_list = "\n".join(f'  {{"id": {t["id"]}, "name": "{t["name"]}"}}' for t in document_types) or "  (leer)"
    tag_list = "\n".join(f'  {{"id": {t["id"]}, "name": "{t["name"]}"}}' for t in tags) or "  (leer)"

    return f"""Du klassifizierst ein Dokument für ein Dokumentenmanagementsystem (paperless-ngx).

AUFGABE 1 — KORRESPONDENT (Absender des Dokuments):
Wähle nach Möglichkeit einen BESTEHENDEN Korrespondenten aus der Liste unten.
Nur wenn eindeutig keiner passt, schlage über "new_correspondent" einen neuen vor.

BESTEHENDE KORRESPONDENTEN:
{corr_list}

AUFGABE 2 — DOKUMENTTYP:
Wähle nach Möglichkeit einen BESTEHENDEN Dokumenttyp.

BESTEHENDE DOKUMENTTYPEN:
{type_list}

AUFGABE 3 — TAGS:
Wähle passende bestehende Tags (0 bis 3). Neue Tags nur wenn wirklich nötig.

BESTEHENDE TAGS:
{tag_list}

Antworte AUSSCHLIESSLICH mit JSON:
{{"correspondent_id": <id oder null>,
 "new_correspondent": "<name oder null>",
 "document_type_id": <id oder null>,
 "new_document_type": "<name oder null>",
 "tag_ids": [<ids>],
 "new_tags": [],
 "reasoning": "<kurze Begründung>"}}

DOKUMENTTEXT:
{text[:MAX_CLASSIFY_CHARS]}"""


def build_metadata_prompt(text: str, filename: str, added: str) -> str:
    return f"""Du extrahierst Metadaten aus einem Dokument.

AUFGABE 1 — TITEL:
Ein kurzer, sprechender Titel (max. 120 Zeichen), der das Dokument im Archiv
wiedererkennbar macht. Kein Dateiname, keine Floskeln.

AUFGABE 2 — DATUM:
Das inhaltliche Datum des Dokuments (Rechnungsdatum, Ausstellungsdatum, Briefdatum)
im Format YYYY-MM-DD. NICHT das Eingangsdatum im Archiv, NICHT Geburtsdaten,
NICHT Fälligkeits- oder Zahlungsfristen.

Antworte AUSSCHLIESSLICH mit JSON:
{{"title": "<titel>", "created": "YYYY-MM-DD", "reasoning": "<kurze Begründung>"}}

HINWEISE: Dateiname: {filename or "unbekannt"}, Eingangsdatum im Archiv: {added}

DOKUMENTTEXT:
{text[:MAX_METADATA_CHARS]}"""
