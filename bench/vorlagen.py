"""Erzeugt die Schreibvorlage aus den Referenztexten unter ``ocr/``.

Die ``.txt``-Dateien sind die Quelle der Wahrheit, diese Übersicht nur eine
lesbare Ansicht davon. Wer den Text ändern will, ändert die ``.txt`` und lässt
diese Datei neu erzeugen — umgekehrt geht verloren.

Blätter ohne zugehöriges PDF sind noch nicht geschrieben und werden als offen
ausgewiesen.
"""

from __future__ import annotations

import sys
from pathlib import Path

from bench import corpus

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "ocr" / "VORLAGEN.md"

HEADER = """# Schreibvorlage

Je ein Dokument auf ein A4-Blatt, von Hand, in normaler Alltagsschrift.

## Ablauf

1. Nicht besonders sauber schreiben — gemessen werden soll der Alltagsfall,
   nicht die Sonntagsschrift.
2. Zeilenumbrüche ungefähr wie unten. Auf die Zeichenfehlerrate wirkt sich das
   nicht aus, Whitespace wird vor dem Vergleich zusammengezogen.
3. Blatt scannen, als PDF, 150 dpi oder mehr.
4. Ablegen unter dem Namen, der in der Überschrift steht.

Danach `python -m bench.corpus` ausführen. Wo ein PDF liegt, kommt das Dokument
in den Korpus; wo keines liegt, fehlt es schlicht. Der Korpus ist also jederzeit
lauffähig.

## Korrekturen sind erwünscht

Durchgestrichene Stellen, krumme Zeilen und Verschreiber gehören dazu — genau
daran unterscheiden sich die Modelle. Der Referenztext ist und bleibt der unten
stehende: eine durchgestrichene Stelle soll das Modell gerade *nicht* lesen.

Weicht das Geschriebene inhaltlich von der Vorlage ab, muss die zugehörige
`.txt` nachgezogen werden. Sonst wird gegen eine Vorlage gemessen, die so nie
auf dem Papier stand.

---
"""


def render() -> str:
    parts = [HEADER]
    for truth in sorted(corpus.SCAN_DIR.glob("*.txt")):
        pdf = truth.with_suffix(".pdf")
        meta, lines = corpus._parse_truth(truth.read_text(encoding="utf-8"))
        text = "\n".join(lines)
        status = "geschrieben" if pdf.exists() else "**offen**"
        parts.append(f"\n## {pdf.name} — {meta.get('title', pdf.stem)}\n")
        parts.append(
            f"*{len([l for l in lines if l.strip()])} Zeilen, "
            f"{len(text.split())} Wörter — {status}*\n"
        )
        if meta:
            parts.append(
                f"Korrespondent: {meta.get('correspondent', '—')} · "
                f"Typ: {meta.get('document_type', '—')} · "
                f"Tags: {meta.get('tags', '—')} · "
                f"Datum: {meta.get('created', '—')}\n"
            )
        parts.append("```text")
        parts.append(text)
        parts.append("```\n")
    return "\n".join(parts)


def main() -> int:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(render(), encoding="utf-8")
    print(f"geschrieben: {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
