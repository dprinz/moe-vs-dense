"""Führt den Benchmark aus.

Nachgestellt wird die Pipeline aus dem Windmill-Script, Stufe für Stufe:

    1. OCR-Check      ist der vorhandene OCR-Text brauchbar?
    2. Vision-OCR     falls nein: Seitenbild lesen
    3. Klassifikation Korrespondent, Dokumenttyp, Tags
    4. Metadaten      Titel und inhaltliches Datum

Stufe 2 läuft nur für Dokumente ohne brauchbares OCR — genau wie produktiv, wo
der Vision-Pfad die Ausnahme ist und nicht der Normalfall. Stufe 3 und 4
arbeiten auf dem Text, den die Pipeline bis dahin hat: beim gedruckten Dokument
der OCR-Text, beim handschriftlichen der selbst gelesene. Damit schlagen Fehler
des Vision-OCR auf die Klassifikation durch, so wie in echt.

Der echte Scan (Variante ``scan``) durchläuft nur Stufe 2. Er ist Fliessprosa
und trägt weder Absender noch Dokumenttyp, für die es eine sinnvolle Ground
Truth gäbe — dafür ist seine Handschrift echt und nicht nachgestellt.

Aufruf:

    python -m bench.run --models qwen3.8:27b qwen3.6:35b-a3b --repeats 3
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from bench import corpus, metrics, ollama, prompts, session, telemetry

ROOT = Path(__file__).resolve().parents[1]
RESULTS_DIR = ROOT / "results"

DEFAULT_BASE_URL = "http://localhost:11434"


def _ref_lists() -> tuple[list[dict], list[dict], list[dict]]:
    """Referenzlisten mit stabilen IDs, wie sie die paperless-API liefern würde."""
    corrs = [{"id": i + 100, "name": n} for i, n in enumerate(corpus.CORRESPONDENTS)]
    types = [{"id": i + 200, "name": n} for i, n in enumerate(corpus.DOCUMENT_TYPES)]
    tags = [{"id": i + 300, "name": n} for i, n in enumerate(corpus.TAGS)]
    return corrs, types, tags


def _name_by_id(items: list[dict], wanted: object) -> str | None:
    for item in items:
        if item["id"] == wanted:
            return item["name"]
    return None


@dataclass
class DocResult:
    doc_id: str
    variant: str
    handwriting: str | None = None
    stages: dict = field(default_factory=dict)
    scores: dict = field(default_factory=dict)
    failed: str | None = None
    skipped: str | None = None
    host: dict | None = None  # Zustand des Rechners zu Beginn des Dokuments


def run_document(
    client: ollama.Client, doc: corpus.Document, has_vision: bool = True
) -> DocResult:
    res = DocResult(doc_id=doc.doc_id, variant=doc.variant, handwriting=doc.handwriting)

    # Ein Modell ohne Vision kann handschriftliche Dokumente nicht bearbeiten.
    # Das ist kein Fehlschlag, sondern eine Eigenschaft des Modells — als
    # Fehler gezählt würde es die Fehlerquote verfälschen, weggelassen wäre
    # unklar, warum es fehlt.
    if not has_vision and doc.variant != "print":
        res.skipped = "Modell kann kein Vision"
        return res

    # --- Der echte Scan: nur OCR ------------------------------------------
    if doc.variant == "scan":
        r = client.generate(prompts.build_vision_prompt(), image=doc.image_path)
        res.stages["vision_ocr"] = r.as_dict()
        if r.error:
            res.failed = f"vision_ocr: {r.error}"
            return res
        text = ollama.strip_think(r.text)
        res.scores["cer"] = metrics.cer(doc.text, text)
        res.scores["wer"] = metrics.wer(doc.text, text)
        res.stages["vision_ocr"]["predicted"] = text
        return res

    corrs, types, tags = _ref_lists()
    ocr_text = corpus.ocr_text_for(doc)

    # --- Stufe 1: OCR-Check -------------------------------------------------
    r1 = client.generate(prompts.build_ocr_prompt(ocr_text))
    res.stages["ocr_check"] = r1.as_dict()
    if r1.error:
        res.failed = f"ocr_check: {r1.error}"
        return res
    try:
        ocr_ok = bool(ollama.extract_json(r1.text).get("ok"))
    except Exception as exc:
        res.failed = f"ocr_check-json: {exc}"
        return res

    # Erwartet: gedruckt = brauchbar, Handschrift = unbrauchbar
    res.scores["ocr_check_correct"] = float(ocr_ok == (doc.variant == "print"))

    # --- Stufe 2: Vision-OCR ------------------------------------------------
    # Wird für alle Handschrift-Dokumente gemessen, auch wenn Stufe 1 sie
    # fälschlich für brauchbar hielt. Sonst hätte ein Modell mit schlechtem
    # OCR-Check gar keine Vision-Messung.
    text = ocr_text
    if doc.variant == "hand":
        r2 = client.generate(prompts.build_vision_prompt(), image=doc.image_path)
        res.stages["vision_ocr"] = r2.as_dict()
        if r2.error:
            res.failed = f"vision_ocr: {r2.error}"
            return res
        text = ollama.strip_think(r2.text)
        res.scores["cer"] = metrics.cer(doc.text, text)
        res.scores["wer"] = metrics.wer(doc.text, text)
        # Den gelesenen Text mitschreiben, nicht nur die Fehlerrate. Eine
        # Zeichenfehlerrate von 35 % sagt nicht, welche Art Fehler dahintersteht
        # — und der interessante Fall ist der, in dem das Modell Unlesbares
        # durch flüssiges, plausibles Deutsch ersetzt statt durch Zeichensalat.
        res.stages["vision_ocr"]["predicted"] = text

    # --- Stufe 3: Klassifikation -------------------------------------------
    r3 = client.generate(prompts.build_classify_prompt(text, corrs, types, tags))
    res.stages["classify"] = r3.as_dict()
    if r3.error:
        res.failed = f"classify: {r3.error}"
        return res
    try:
        cls = ollama.extract_json(r3.text)
    except Exception as exc:
        res.failed = f"classify-json: {exc}"
        return res

    got_corr = _name_by_id(corrs, cls.get("correspondent_id"))
    got_type = _name_by_id(types, cls.get("document_type_id"))
    got_tags = [n for n in (_name_by_id(tags, t) for t in cls.get("tag_ids") or []) if n]

    res.scores["correspondent_correct"] = float(metrics.exact(doc.correspondent, got_corr))
    res.scores["document_type_correct"] = float(metrics.exact(doc.document_type, got_type))
    res.scores["tag_f1"] = metrics.f1(doc.tags, got_tags)
    res.stages["classify"]["predicted"] = {
        "correspondent": got_corr,
        "document_type": got_type,
        "tags": got_tags,
    }

    # --- Stufe 4: Metadaten -------------------------------------------------
    r4 = client.generate(
        prompts.build_metadata_prompt(text, f"{doc.doc_id}.pdf", doc.created or "")
    )
    res.stages["metadata"] = r4.as_dict()
    if r4.error:
        res.failed = f"metadata: {r4.error}"
        return res
    try:
        meta = ollama.extract_json(r4.text)
    except Exception as exc:
        res.failed = f"metadata-json: {exc}"
        return res

    res.scores["date_correct"] = float(metrics.exact(doc.created, meta.get("created")))
    res.scores["title_f1"] = metrics.title_f1(doc.title, meta.get("title") or "")
    res.stages["metadata"]["predicted"] = {
        "title": meta.get("title"),
        "created": meta.get("created"),
    }

    return res


def run_model(
    base_url: str,
    model: str,
    docs: list[corpus.Document],
    repeats: int,
    session_record: dict | None = None,
) -> dict:
    client = ollama.Client(base_url=base_url, model=model)
    print(f"\n=== {model} ===", flush=True)
    print("  warmup ...", end=" ", flush=True)
    w = client.warmup()
    if w.error:
        print(f"FEHLER: {w.error}")
        return {"model": model, "error": w.error, "session": session_record}
    print(f"ok ({w.load_s:.1f}s Ladezeit)", flush=True)

    info = ollama.info(base_url, model)
    has_vision = "vision" in (info.get("capabilities") or [])
    if not has_vision:
        print("  kein Vision — nur gedruckte Dokumente", flush=True)

    runs: list[list[DocResult]] = []
    uptime_start = session.uptime_s(base_url)
    started = time.perf_counter()
    for rep in range(repeats):
        pass_results: list[DocResult] = []
        for doc in docs:
            t0 = time.perf_counter()
            host = telemetry.sample(base_url)
            res = run_document(client, doc, has_vision=has_vision)
            res.host = host
            dt = time.perf_counter() - t0
            mark = "UEBR" if res.skipped else ("OK  " if not res.failed else "FEHL")
            print(
                f"  [{rep + 1}/{repeats}] {doc.doc_id} {doc.variant:5s} "
                f"{mark} {dt:6.1f}s",
                flush=True,
            )
            if res.failed:
                print(f"        {res.failed}", flush=True)
            pass_results.append(res)
        runs.append(pass_results)
    total = time.perf_counter() - started

    client.unload()
    return {
        "model": model,
        "info": info,
        "repeats": repeats,
        "total_wall_s": round(total, 1),
        # Wie alt die Ollama-Session zu Beginn und am Ende der Messung war.
        # Ohne diese beiden Zahlen lässt sich hinterher nicht mehr sagen, ob ein
        # Modell langsam war oder bloss spät dran.
        "session": {
            **(session_record or {}),
            "uptime_at_start_s": uptime_start,
            "uptime_at_end_s": session.uptime_s(base_url),
        },
        "runs": [[vars(r) for r in rep] for rep in runs],
    }


def _spread(values: list[float | None]) -> dict | None:
    """Streuung einer Grösse über die Wiederholungen.

    Der Mittelwert allein trägt hier nicht: derselbe Lauf desselben Modells auf
    demselben Bild lieferte Zeichenfehlerraten von 39 % und 74 %. Wer nur den
    Mittelwert ausweist, verkauft einen Zufallswert als Messergebnis. Deshalb
    stehen Standardabweichung, Spannweite und die Einzelwerte daneben.
    """
    vals = [float(v) for v in values if v is not None]
    if not vals:
        return None
    return {
        "mean": round(metrics.mean(vals), 4),
        "stdev": round(statistics.stdev(vals), 4) if len(vals) > 1 else 0.0,
        "min": round(min(vals), 4),
        "max": round(max(vals), 4),
        "runs": [round(v, 4) for v in vals],
    }


def _host_summary(samples: list[dict]) -> dict | None:
    """Verdichtet die Hostmessungen auf das, was eine Degradation zeigen würde.

    Steigt die Speicherbelegung des Runners über den Lauf, fällt der freie
    Speicher, wächst der Swap oder meldet der Rechner eine thermische
    Begrenzung, steht es hier — und zwar unabhängig davon, ob die Zeiten
    auffällig waren. Erst beides nebeneinander erlaubt eine Aussage über
    Ursache und Wirkung.
    """
    if not samples:
        return None

    def series(path: tuple[str, ...]) -> list[float]:
        out = []
        for sample in samples:
            node: object = sample
            for key in path:
                node = (node or {}).get(key) if isinstance(node, dict) else None
            if node is not None:
                out.append(float(node))
        return out

    free = series(("memory", "free_gb"))
    swap = series(("memory", "swap_used_mb"))
    rss = series(("runner_rss_gb",))
    limits = series(("thermal", "cpu_speed_limit"))
    return {
        "samples": len(samples),
        "runner_rss_gb": {"first": rss[0], "last": rss[-1], "max": max(rss)} if rss else None,
        "free_gb": {"first": free[0], "last": free[-1], "min": min(free)} if free else None,
        "swap_used_mb": {"first": swap[0], "last": swap[-1], "max": max(swap)} if swap else None,
        "cpu_speed_limit_min": min(limits) if limits else None,
        "thermally_limited": any(v < 100 for v in limits),
    }


def summarize(model_result: dict) -> dict:
    """Verdichtet die Einzelläufe zu Mittelwerten je Metrik und Stufe."""
    if model_result.get("error"):
        return {"model": model_result["model"], "error": model_result["error"]}

    everything = [r for rep in model_result["runs"] for r in rep]
    skipped = [r for r in everything if r.get("skipped")]
    flat = [r for r in everything if not r.get("skipped")]
    ok = [r for r in flat if not r["failed"]]

    def score(name: str, subset: list[dict] | None = None) -> float | None:
        # Auf `is None` prüfen, nicht auf Wahrheitswert: eine leere Teilmenge
        # bedeutet "dafür gibt es keine Dokumente" und muss None ergeben. Mit
        # `subset or ok` fiel sie auf den Gesamtkorpus zurück und lieferte eine
        # Zahl, die aussah wie ein Messwert, aber eine andere Gruppe beschrieb.
        rows = ok if subset is None else subset
        vals = [r["scores"][name] for r in rows if name in r["scores"]]
        return round(metrics.mean(vals), 4) if vals else None

    # Getrennt ausgewiesen, weil ein Handschrift-Font deutlich leichter zu lesen
    # ist als echte Handschrift. Die beiden Zahlen zusammenzuwerfen würde die
    # Fehlerrate schönen.
    echt = [r for r in ok if r.get("handwriting") == "echt"]
    font = [r for r in ok if r.get("handwriting") == "font"]

    # Ein Modell ohne Vision bearbeitet nur die gedruckten Dokumente. Seine
    # Genauigkeit gegen die der anderen zu stellen vergleicht zwei verschiedene
    # Aufgaben — und lässt das kleine Modell gut aussehen, weil ihm der schwere
    # Teil des Korpus erspart bleibt. Die gedruckte Teilmenge ist der einzige
    # Boden, auf dem alle Modelle dieselbe Arbeit geleistet haben.
    printed = [r for r in ok if r["variant"] == "print"]

    stage_stats: dict[str, dict] = {}
    for stage in ("ocr_check", "vision_ocr", "classify", "metadata"):
        walls = [r["stages"][stage]["wall_s"] for r in flat if stage in r["stages"]]
        rates = [
            r["stages"][stage]["tokens_per_s"]
            for r in flat
            if stage in r["stages"] and r["stages"][stage]["tokens_per_s"] > 0
        ]
        toks = [float(r["stages"][stage]["eval_tokens"]) for r in flat if stage in r["stages"]]
        if not walls:
            continue
        stage_stats[stage] = {
            "calls": len(walls),
            "wall_s_mean": round(metrics.mean(walls), 2),
            "wall_s_median": round(statistics.median(walls), 2),
            "tokens_per_s_mean": round(metrics.mean(rates), 2) if rates else None,
            "eval_tokens_mean": round(metrics.mean(toks), 1),
        }

    doc_walls = [
        sum(s["wall_s"] for s in r["stages"].values())
        for r in flat
        if r["stages"] and r["variant"] != "scan"
    ]

    # Je Wiederholung ein Mittelwert, daraus die Streuung. Über alle Läufe
    # gemittelt wäre die Streuung nicht mehr sichtbar — genau sie entscheidet
    # aber, ob ein Genauigkeitsunterschied zwischen zwei Modellen etwas bedeutet.
    def per_repeat(name: str, keep=lambda r: True) -> list[float | None]:
        out: list[float | None] = []
        for rep in model_result["runs"]:
            vals = [
                r["scores"][name]
                for r in rep
                if not r.get("skipped") and not r["failed"] and name in r["scores"] and keep(r)
            ]
            out.append(metrics.mean(vals) if vals else None)
        return out

    spread = {
        "ocr_check_correct": _spread(per_repeat("ocr_check_correct")),
        "cer_echte_handschrift": _spread(per_repeat("cer", lambda r: r.get("handwriting") == "echt")),
        "wer_echte_handschrift": _spread(per_repeat("wer", lambda r: r.get("handwriting") == "echt")),
        "cer_font": _spread(per_repeat("cer", lambda r: r.get("handwriting") == "font")),
        "wer_font": _spread(per_repeat("wer", lambda r: r.get("handwriting") == "font")),
        "correspondent_correct": _spread(per_repeat("correspondent_correct")),
        "document_type_correct": _spread(per_repeat("document_type_correct")),
        "tag_f1": _spread(per_repeat("tag_f1")),
        "date_correct": _spread(per_repeat("date_correct")),
        "title_f1": _spread(per_repeat("title_f1")),
    }

    # Je Dokument über die Wiederholungen: hier wird sichtbar, ob ein einzelnes
    # Dokument die gesamte Streuung des Modells erzeugt.
    per_document: dict[str, dict] = {}
    for doc_id in dict.fromkeys(r["doc_id"] for r in flat):
        rows = [
            next((r for r in rep if r["doc_id"] == doc_id), None)
            for rep in model_result["runs"]
        ]
        rows = [r for r in rows if r is not None and not r.get("skipped")]
        good = [r for r in rows if not r["failed"]]
        entry: dict = {
            "variant": rows[0]["variant"],
            "handwriting": rows[0].get("handwriting"),
            "runs": len(rows),
            "failed": len(rows) - len(good),
        }
        for name in ("cer", "wer", "tag_f1", "title_f1", "correspondent_correct",
                     "document_type_correct", "date_correct"):
            value = _spread([r["scores"].get(name) for r in good])
            if value is not None:
                entry[name] = value
        entry["wall_s"] = _spread(
            [sum(st["wall_s"] for st in r["stages"].values()) for r in good if r["stages"]]
        )
        per_document[doc_id] = entry

    return {
        "model": model_result["model"],
        "info": model_result.get("info", {}),
        "documents_total": len(flat),
        "documents_skipped": len(skipped),
        "skip_reason": skipped[0]["skipped"] if skipped else None,
        "documents_ok": len(ok),
        "documents_failed": len(flat) - len(ok),
        "failures": [r["failed"] for r in flat if r["failed"]],
        "accuracy": {
            "ocr_check_correct": score("ocr_check_correct"),
            "cer_echte_handschrift": score("cer", echt),
            "wer_echte_handschrift": score("wer", echt),
            "cer_font": score("cer", font),
            "wer_font": score("wer", font),
            "correspondent_correct": score("correspondent_correct"),
            "document_type_correct": score("document_type_correct"),
            "tag_f1": score("tag_f1"),
            "date_correct": score("date_correct"),
            "title_f1": score("title_f1"),
        },
        "accuracy_print_only": {
            "documents": len(printed),
            "ocr_check_correct": score("ocr_check_correct", printed),
            "correspondent_correct": score("correspondent_correct", printed),
            "document_type_correct": score("document_type_correct", printed),
            "tag_f1": score("tag_f1", printed),
            "date_correct": score("date_correct", printed),
            "title_f1": score("title_f1", printed),
        },
        "accuracy_spread": spread,
        "per_document": per_document,
        "session": model_result.get("session"),
        "host": _host_summary([r["host"] for r in everything if r.get("host")]),
        "speed": {
            "wall_s_per_document_mean": round(metrics.mean(doc_walls), 2),
            # Ein Mittelwert je Wiederholung: steigt er von Durchlauf zu
            # Durchlauf, ist nicht das Modell langsam, sondern die Session alt.
            "wall_s_per_document_by_repeat": [
                round(metrics.mean([
                    sum(st["wall_s"] for st in r["stages"].values())
                    for r in rep
                    if not r.get("skipped") and r["stages"] and r["variant"] != "scan"
                ]), 2)
                for rep in model_result["runs"]
                if any(not r.get("skipped") and r["stages"] for r in rep)
            ],
            "total_wall_s": model_result["total_wall_s"],
            "stages": stage_stats,
        },
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="MoE gegen dense auf der paperless-Pipeline")
    ap.add_argument("--base-url", default=DEFAULT_BASE_URL, help="Ollama-Endpunkt")
    ap.add_argument(
        "--models", nargs="+", help="Modelle in Reihenfolge der Messung"
    )
    ap.add_argument(
        "--resummarize",
        metavar="ERGEBNIS.json",
        help="Zusammenfassung aus vorhandenen Rohdaten neu rechnen, ohne zu messen",
    )
    ap.add_argument("--repeats", type=int, default=3, help="Durchläufe je Modell")
    ap.add_argument("--only", nargs="*", help="nur diese doc_ids messen")
    ap.add_argument(
        "--restart-between-models",
        action="store_true",
        help="Ollama vor jedem Modell neu starten (jedes Modell misst in frischer Session)",
    )
    ap.add_argument(
        "--restart-cmd",
        default=None,
        help=f"Kommando für den Neustart, Vorgabe: {session.DEFAULT_RESTART_CMD!r}",
    )
    ap.add_argument("--out", default=None, help="Zieldatei für das Rohergebnis")
    args = ap.parse_args(argv)

    # Ändert sich die Auswertung, sollen die Zahlen eines Laufs nachziehbar
    # sein, ohne ihn zu wiederholen — vier Modelle über acht Dokumente sind
    # Stunden Rechenzeit, die Auswertung ist Millisekunden.
    if args.resummarize:
        path = Path(args.resummarize)
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["summary"] = [summarize(r) for r in payload["raw"]]
        payload["resummarized_at"] = datetime.now(timezone.utc).isoformat()
        text = json.dumps(payload, indent=2, ensure_ascii=False)
        path.write_text(text, encoding="utf-8")
        (RESULTS_DIR / "latest.json").write_text(text, encoding="utf-8")
        print(f"Zusammenfassung neu gerechnet: {path}")
        return 0

    if not args.models:
        ap.error("--models wird gebraucht, wenn nicht --resummarize angegeben ist")

    if args.restart_cmd and not args.restart_between_models:
        ap.error("--restart-cmd ohne --restart-between-models bleibt wirkungslos")

    docs = corpus.build()
    if args.only:
        docs = [d for d in docs if d.doc_id in set(args.only)]
    print(
        f"Korpus: {len(docs)} Dokumente "
        f"({sum(d.variant == 'print' for d in docs)} gedruckt, "
        f"{sum(d.handwriting == 'echt' for d in docs)} echte Handschrift, "
        f"{sum(d.handwriting == 'font' for d in docs)} Handschrift-Font)"
    )

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = Path(args.out) if args.out else RESULTS_DIR / f"raw-{stamp}.json"

    def persist(results: list[dict]) -> None:
        payload = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "base_url": args.base_url,
            # Ohne die Maschine sind zwei Ergebnisdateien nicht vergleichbar,
            # und im JSON sieht man ihr den Rechner nicht an.
            "host": telemetry.host_info(),
            "restart_between_models": args.restart_between_models,
            "repeats": args.repeats,
            "documents": [d.doc_id for d in docs],
            "models_requested": args.models,
            "models_done": [r["model"] for r in results],
            "raw": results,
            "summary": [summarize(r) for r in results],
        }
        text = json.dumps(payload, indent=2, ensure_ascii=False)
        out.write_text(text, encoding="utf-8")
        (RESULTS_DIR / "latest.json").write_text(text, encoding="utf-8")

    # Nach jedem Modell schreiben, nicht erst am Ende. Ein Lauf über mehrere
    # Modelle dauert Stunden; bricht er in der Mitte ab — Modell abgestürzt,
    # Maschine überlastet, Abbruch von Hand — wären sonst auch die bereits
    # fertig gemessenen Modelle verloren.
    results: list[dict] = []
    for model in args.models:
        # Vor jedem Modell eine frische Session. Sonst misst der spätere Teil
        # des Laufs eine Ollama-Instanz, die schon Stunden auf dem Buckel hat —
        # und langsamere Modelle stehen naturgemäss weiter hinten.
        record: dict | None = None
        if args.restart_between_models:
            print(f"\nOllama neu starten vor {model} ...", end=" ", flush=True)
            record = session.restart(args.base_url, args.restart_cmd)
            print(
                f"{'ok' if record['restarted'] else 'FEHLGESCHLAGEN'} "
                f"({record['wait_s']:.0f}s, Session war {record['uptime_before_s']}s alt)",
                flush=True,
            )
            if not record["restarted"]:
                print("  Endpunkt antwortet nicht — Abbruch", flush=True)
                break
        results.append(run_model(args.base_url, model, docs, args.repeats, record))
        persist(results)
        print(f"  → gesichert nach {out.name}", flush=True)

    print(f"\nRohdaten: {out}\nZusammenfassung: {RESULTS_DIR / 'latest.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
