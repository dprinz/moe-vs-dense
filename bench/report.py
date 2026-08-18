"""Erzeugt aus ``results/latest.json`` eine Markdown-Tabelle.

Bewusst schlicht: die Zahlen sollen sich in einen Artikel kopieren lassen, ohne
dass jemand sie von Hand aus dem JSON klaubt und sich dabei vertippt.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

ACCURACY_LABELS = [
    ("ocr_check_correct", "OCR-Check richtig", "quote"),
    ("cer_echte_handschrift", "Zeichenfehlerrate echte Handschrift", "rate"),
    ("wer_echte_handschrift", "Wortfehlerrate echte Handschrift", "rate"),
    ("cer_font", "Zeichenfehlerrate Handschrift-Font", "rate"),
    ("wer_font", "Wortfehlerrate Handschrift-Font", "rate"),
    ("correspondent_correct", "Korrespondent richtig", "quote"),
    ("document_type_correct", "Dokumenttyp richtig", "quote"),
    ("tag_f1", "Tags F1", "score"),
    ("date_correct", "Datum richtig", "quote"),
    ("title_f1", "Titel F1", "score"),
]

STAGE_LABELS = {
    "ocr_check": "OCR-Check",
    "vision_ocr": "Vision-OCR",
    "classify": "Klassifikation",
    "metadata": "Metadaten",
}


def _fmt(value: object, kind: str) -> str:
    if value is None:
        return "—"
    if kind == "quote":
        return f"{float(value) * 100:.0f} %"
    if kind == "rate":
        return f"{float(value) * 100:.1f} %"
    return f"{float(value):.2f}"


def render(payload: dict) -> str:
    summaries = payload["summary"]
    names = [s["model"] for s in summaries]
    head = " | ".join(names)
    sep = " | ".join("---" for _ in names)

    out: list[str] = []
    host = payload.get("host") or {}
    out.append(f"Gemessen am {payload['generated_at'][:19].replace('T', ' ')} UTC, "
               f"{payload['repeats']} Durchläufe je Modell, "
               f"{len(payload['documents'])} Dokumente.\n")
    if host:
        out.append(
            f"Rechner: {host.get('cpu')}, {host.get('ram_gb')} GB, "
            f"{host.get('ollama_version') or 'Ollama'}. "
            + ("Ollama vor jedem Modell neu gestartet.\n"
               if payload.get("restart_between_models")
               else "**Ohne Neustart zwischen den Modellen** — spätere Modelle "
                    "messen eine ältere Session mit.\n")
        )

    out.append("## Modelle\n")
    out.append(f"| | {head} |")
    out.append(f"| --- | {sep} |")
    for field, label in (
        ("parameter_size", "Parameter"),
        ("quantization", "Quantisierung"),
        ("family", "Familie"),
    ):
        cells = " | ".join(str(s.get("info", {}).get(field) or "—") for s in summaries)
        out.append(f"| {label} | {cells} |")

    out.append("\n## Genauigkeit\n")
    out.append(f"| Metrik | {head} |")
    out.append(f"| --- | {sep} |")
    for key, label, kind in ACCURACY_LABELS:
        cells = " | ".join(_fmt(s["accuracy"].get(key), kind) for s in summaries)
        out.append(f"| {label} | {cells} |")

    # Getrennte Tabelle, weil ein Modell ohne Vision oben nur die gedruckten
    # Dokumente bewertet bekommt: erst hier stehen alle Modelle auf derselben
    # Aufgabe.
    if any(s.get("accuracy_print_only") for s in summaries):
        counts = {s["accuracy_print_only"]["documents"] for s in summaries}
        out.append("\n## Genauigkeit, nur gedruckte Dokumente\n")
        out.append("Die Teilmenge, die jedes Modell bearbeitet — auch eines ohne "
                   f"Vision. {min(counts)} Dokumentläufe je Modell.\n")
        out.append(f"| Metrik | {head} |")
        out.append(f"| --- | {sep} |")
        for key, label, kind in ACCURACY_LABELS:
            if key not in summaries[0]["accuracy_print_only"]:
                continue
            cells = " | ".join(
                _fmt(s["accuracy_print_only"].get(key), kind) for s in summaries
            )
            out.append(f"| {label} | {cells} |")

    out.append("\n## Geschwindigkeit\n")
    out.append(f"| | {head} |")
    out.append(f"| --- | {sep} |")
    cells = " | ".join(
        f"{s['speed']['wall_s_per_document_mean']:.0f} s" for s in summaries
    )
    out.append(f"| Sekunden je Dokument | {cells} |")
    for stage, label in STAGE_LABELS.items():
        rates = []
        for s in summaries:
            st = s["speed"]["stages"].get(stage)
            rates.append(f"{st['tokens_per_s_mean']:.1f}" if st and st["tokens_per_s_mean"] else "—")
        out.append(f"| {label} Tokens/s | {' | '.join(rates)} |")
    for stage, label in STAGE_LABELS.items():
        walls = []
        for s in summaries:
            st = s["speed"]["stages"].get(stage)
            walls.append(f"{st['wall_s_mean']:.0f} s" if st else "—")
        out.append(f"| {label} Dauer | {' | '.join(walls)} |")

    # Streuung getrennt ausweisen, nicht als ± hinter den Mittelwert: bei drei
    # Durchläufen ist sie kein Fehlerbalken, sondern ein Warnhinweis darauf,
    # welche Zahl oben nicht belastbar ist.
    if any(s.get("accuracy_spread") for s in summaries):
        out.append("\n## Streuung über die Durchläufe\n")
        out.append("Spannweite der Mittelwerte je Durchlauf. Wo sie in der "
                   "Grössenordnung des Modellunterschieds liegt, trägt der "
                   "Vergleich nicht.\n")
        out.append(f"| Metrik | {head} |")
        out.append(f"| --- | {sep} |")
        for key, label, kind in ACCURACY_LABELS:
            cells = []
            for s in summaries:
                sp = (s.get("accuracy_spread") or {}).get(key)
                cells.append(
                    f"{_fmt(sp['min'], kind)} – {_fmt(sp['max'], kind)}"
                    if sp and sp["stdev"] else ("konstant" if sp else "—")
                )
            out.append(f"| {label} | {' | '.join(cells)} |")

    # Je Dokument, weil ein einzelnes Blatt die gesamte Streuung erzeugen kann.
    docs_with_cer = sorted({
        doc_id
        for s in summaries
        for doc_id, entry in (s.get("per_document") or {}).items()
        if "cer" in entry
    })
    if docs_with_cer:
        out.append("\n## Zeichenfehlerrate je Dokument\n")
        out.append(f"| Dokument | Schrift | {head} |")
        out.append(f"| --- | --- | {sep} |")
        for doc_id in docs_with_cer:
            kind_cell = ""
            cells = []
            for s in summaries:
                entry = (s.get("per_document") or {}).get(doc_id) or {}
                kind_cell = entry.get("handwriting") or kind_cell
                cer = entry.get("cer")
                if not cer:
                    cells.append("—")
                elif cer["stdev"]:
                    cells.append(
                        f"{cer['mean'] * 100:.1f} % ({cer['min'] * 100:.1f}–{cer['max'] * 100:.1f})"
                    )
                else:
                    cells.append(f"{cer['mean'] * 100:.1f} %")
            out.append(f"| {doc_id} | {kind_cell or '—'} | {' | '.join(cells)} |")

    # Belegt oder entkräftet den Verdacht, dass eine alternde Ollama-Session
    # mitgemessen wird: die drei Durchläufe eines Modells sind gleichartig.
    if any(s.get("speed", {}).get("wall_s_per_document_by_repeat") for s in summaries):
        out.append("\n## Sekunden je Dokument, Durchlauf für Durchlauf\n")
        out.append(f"| Durchlauf | {head} |")
        out.append(f"| --- | {sep} |")
        depth = max(len(s["speed"].get("wall_s_per_document_by_repeat") or []) for s in summaries)
        for i in range(depth):
            cells = []
            for s in summaries:
                series = s["speed"].get("wall_s_per_document_by_repeat") or []
                cells.append(f"{series[i]:.0f} s" if i < len(series) else "—")
            out.append(f"| {i + 1} | {' | '.join(cells)} |")

    if any(s.get("host") for s in summaries):
        out.append("\n## Zustand des Rechners\n")
        out.append(f"| | {head} |")
        out.append(f"| --- | {sep} |")
        rows = [
            ("Runner-Speicher zuletzt", lambda h: f"{h['runner_rss_gb']['last']:.1f} GB"
             if h.get("runner_rss_gb") else "—"),
            ("freier Speicher, Minimum", lambda h: f"{h['free_gb']['min']:.1f} GB"
             if h.get("free_gb") else "—"),
            ("Swap, Maximum", lambda h: f"{h['swap_used_mb']['max']:.0f} MB"
             if h.get("swap_used_mb") else "—"),
            ("thermisch gedrosselt", lambda h: "ja" if h.get("thermally_limited") else "nein"),
        ]
        for label, fmt in rows:
            cells = " | ".join(fmt(s["host"]) if s.get("host") else "—" for s in summaries)
            out.append(f"| {label} | {cells} |")

    sessions = [(s["model"], s.get("session") or {}) for s in summaries]
    if any(sess.get("uptime_at_start_s") is not None for _, sess in sessions):
        out.append("\n## Alter der Ollama-Session\n")
        out.append(f"| | {head} |")
        out.append(f"| --- | {sep} |")
        for label, key in (("bei Messbeginn", "uptime_at_start_s"), ("am Ende", "uptime_at_end_s")):
            cells = " | ".join(
                f"{sess[key] / 60:.0f} min" if sess.get(key) is not None else "—"
                for _, sess in sessions
            )
            out.append(f"| {label} | {cells} |")

    failures = [(s["model"], s["failures"]) for s in summaries if s.get("failures")]
    if failures:
        out.append("\n## Fehlschläge\n")
        for model, fails in failures:
            out.append(f"- **{model}**: {len(fails)}")
            for f in dict.fromkeys(fails):
                out.append(f"  - {f}")

    return "\n".join(out) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Markdown-Bericht aus einem Benchmark-Lauf")
    ap.add_argument("--input", default=str(ROOT / "results" / "latest.json"))
    ap.add_argument("--output", default=str(ROOT / "results" / "report.md"))
    args = ap.parse_args(argv)

    payload = json.loads(Path(args.input).read_text(encoding="utf-8"))
    text = render(payload)
    Path(args.output).write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
