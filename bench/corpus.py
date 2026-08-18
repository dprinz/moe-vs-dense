"""Dokumentkorpus mit exakter Ground Truth.

Zwei Quellen, aus einem Grund getrennt:

* **Gedruckt** (``d01``–``d04``): erfundene Dokumente, im Code definiert und als
  PNG gerendert. Niemand schreibt eine gedruckte Rechnung von Hand ab, und für
  die Klassifikation ist der saubere Fall der Normalfall.

* **Handschriftlich** (``ocr/``): tatsächlich von Hand geschriebene und
  eingescannte Blätter. Je ein ``<name>.pdf`` mit einem ``<name>.txt`` daneben,
  das den Referenztext trägt und optional einen Metadatenkopf.

Der Referenztext liegt bewusst beim Scan und nicht im Code. Was auf dem Papier
steht, entscheidet die Person mit dem Stift; eine zweite Fassung im Code liefe
früher oder später auseinander, und die Zeichenfehlerrate würde dann gegen die
falsche Vorlage gemessen.

Format der ``.txt``::

    correspondent: Musikschule Talgrund
    document_type: Kontaktliste
    tags: bildung, freizeit
    title: Kontaktliste Blockflötengruppe Mittwoch
    created: 2026-08-12
    ---
    <Referenztext, Zeile für Zeile wie auf dem Blatt>

Mit Kopf wird die volle Pipeline gemessen, ohne Kopf nur das OCR. Eine ``.txt``
ohne zugehöriges PDF ist ein geplantes Blatt und wird übersprungen — so lassen
sich Vorlagen ablegen, bevor jemand sie abgeschrieben hat.
"""

from __future__ import annotations

import json
import random
import unicodedata
from dataclasses import asdict, dataclass, field
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
CORPUS_DIR = ROOT / "corpus"
SCAN_DIR = ROOT / "ocr"

# macOS-Systemfonts. Bewusst keine Downloads: der Korpus soll sich auf dem
# Rechner reproduzieren lassen, auf dem auch Ollama läuft.
FONT_PRINT = "/System/Library/Fonts/Supplemental/Arial.ttf"
FONT_HAND = "/System/Library/Fonts/Supplemental/Bradley Hand Bold.ttf"

PAGE_W, PAGE_H = 1240, 1754  # A4 bei 150 dpi, wie VISION_DPI im Windmill-Script
SCAN_DPI = 150


@dataclass
class Document:
    """Ein Testdokument samt allem, was gemessen werden soll.

    ``variant`` steuert, welche Stufen gemessen werden:

    * ``print``  gedruckt, OCR ist brauchbar → Klassifikation ohne Vision
    * ``hand``   Handschrift-Font, OCR unbrauchbar → Vision plus Klassifikation
    * ``scan``   echter Scan → nur Vision-OCR
    """

    doc_id: str
    variant: str
    title: str
    lines: list[str]
    correspondent: str | None = None
    document_type: str | None = None
    tags: list[str] = field(default_factory=list)
    created: str | None = None
    source_pdf: str | None = None
    handwriting: str | None = None  # "font" | "echt"
    notes: str = ""

    @property
    def text(self) -> str:
        return "\n".join(self.lines)

    @property
    def image_path(self) -> Path:
        if self.source_pdf is not None:
            return SCAN_DIR / f"{self.doc_id}-page1.png"
        return CORPUS_DIR / f"{self.doc_id}-{self.variant}.png"

    @property
    def classifies(self) -> bool:
        """Ob für dieses Dokument Klassifikation und Metadaten gemessen werden."""
        return self.variant in ("print", "hand")


# ---------------------------------------------------------------------------
# Referenzlisten — das, was in paperless bereits existiert
# ---------------------------------------------------------------------------

CORRESPONDENTS = [
    "Stadtwerke Hallwil",
    "Kantonsspital Nordheim",
    "Versicherung Steinbach AG",
    "Musikschule Talgrund",
    "Garage Wenger GmbH",
    "Gemeindeverwaltung Amriswil",
    "Bibliothek Seefeld",
    "Zahnarztpraxis Dr. Lehner",
]

DOCUMENT_TYPES = [
    "Rechnung",
    "Vertrag",
    "Mahnung",
    "Anmeldeformular",
    "Arztbericht",
    "Kontaktliste",
    "Bestätigung",
]

TAGS = [
    "finanzen",
    "gesundheit",
    "versicherung",
    "wohnen",
    "bildung",
    "fahrzeug",
    "behörde",
    "freizeit",
]


# ---------------------------------------------------------------------------
# Die synthetischen Dokumente
# ---------------------------------------------------------------------------

def _synthetic() -> list[Document]:
    return [
        Document(
            doc_id="d01",
            variant="print",
            correspondent="Stadtwerke Hallwil",
            document_type="Rechnung",
            tags=["finanzen", "wohnen"],
            title="Stromabrechnung 2. Quartal 2026",
            created="2026-07-04",
            lines=[
                "Stadtwerke Hallwil",
                "Werkstrasse 12, 8570 Hallwil",
                "",
                "Rechnung Nr. 2026-04417",
                "Rechnungsdatum: 04.07.2026",
                "Kundennummer: 88-4412-7",
                "",
                "Stromabrechnung 2. Quartal 2026",
                "Abrechnungszeitraum: 01.04.2026 bis 30.06.2026",
                "",
                "Verbrauch Hochtarif      412 kWh      98.88 CHF",
                "Verbrauch Niedertarif    286 kWh      45.76 CHF",
                "Grundgebühr                          24.00 CHF",
                "Netznutzung                          61.20 CHF",
                "",
                "Zwischensumme                       229.84 CHF",
                "Mehrwertsteuer 8.1 Prozent           18.62 CHF",
                "Rechnungsbetrag                     248.46 CHF",
                "",
                "Zahlbar bis 03.08.2026 ohne Abzug.",
            ],
        ),
        Document(
            doc_id="d02",
            variant="print",
            correspondent="Versicherung Steinbach AG",
            document_type="Vertrag",
            tags=["versicherung", "wohnen"],
            title="Hausratversicherung Policenänderung",
            created="2026-05-19",
            lines=[
                "Versicherung Steinbach AG",
                "Postfach 220, 3000 Bern",
                "",
                "Policenänderung zur Hausratversicherung",
                "Policennummer: HR-771-9048",
                "Datum: 19.05.2026",
                "",
                "Sehr geehrter Versicherungsnehmer",
                "",
                "Wir bestätigen Ihnen die Anpassung der Versicherungssumme",
                "per 01.06.2026. Die neue Versicherungssumme beträgt",
                "120000 CHF. Der Jahresbeitrag ändert sich dadurch von",
                "384.00 CHF auf 431.00 CHF.",
                "",
                "Der Selbstbehalt bleibt unverändert bei 200 CHF je",
                "Schadenfall. Alle übrigen Vertragsbedingungen gelten",
                "unverändert weiter.",
                "",
                "Freundliche Grüsse",
                "Versicherung Steinbach AG",
            ],
        ),
        Document(
            doc_id="d03",
            variant="print",
            correspondent="Garage Wenger GmbH",
            document_type="Rechnung",
            tags=["fahrzeug", "finanzen"],
            title="Servicearbeiten Jahreswartung",
            created="2026-06-11",
            lines=[
                "Garage Wenger GmbH",
                "Industriestrasse 4, 9000 Talgrund",
                "",
                "Rechnung 6621",
                "Datum: 11.06.2026",
                "Fahrzeug: Kombi, Jahrgang 2019",
                "Kilometerstand: 84210",
                "",
                "Jahreswartung",
                "",
                "Motoröl und Filter wechseln           142.00 CHF",
                "Bremsflüssigkeit ersetzen              88.00 CHF",
                "Pollenfilter                           46.50 CHF",
                "Arbeitszeit 2.5 Stunden               287.50 CHF",
                "",
                "Total inkl. Mehrwertsteuer            564.00 CHF",
                "",
                "Zahlbar innert 30 Tagen.",
            ],
        ),
        Document(
            doc_id="d04",
            variant="print",
            correspondent="Gemeindeverwaltung Amriswil",
            document_type="Bestätigung",
            tags=["behörde", "wohnen"],
            title="Wohnsitzbestätigung",
            created="2026-04-28",
            lines=[
                "Gemeindeverwaltung Amriswil",
                "Einwohnerdienste",
                "Rathausplatz 1, 8580 Amriswil",
                "",
                "Wohnsitzbestätigung",
                "Ausgestellt am 28.04.2026",
                "Geschäftsnummer: EW-2026-3391",
                "",
                "Hiermit wird bestätigt, dass die antragstellende Person",
                "seit dem 01.09.2021 ununterbrochen in der Gemeinde",
                "Amriswil angemeldet ist.",
                "",
                "Diese Bestätigung dient zur Vorlage bei Behörden und",
                "ist ohne Unterschrift gültig.",
                "",
                "Einwohnerdienste Amriswil",
            ],
        ),
        Document(
            doc_id="d05",
            variant="hand",
            correspondent="Musikschule Talgrund",
            document_type="Kontaktliste",
            tags=["bildung", "freizeit"],
            title="Kontaktliste Blockflötengruppe Mittwoch",
            created="2026-08-12",
            lines=[
                "Musikschule Talgrund",
                "Kontaktliste Blockflötengruppe Mittwoch",
                "Stand 12.08.2026",
                "",
                "Teilnehmer 1   079 400 11 22   erreichbar ab 17 Uhr",
                "Teilnehmer 2   079 400 33 44   nur Festnetz",
                "Teilnehmer 3   079 400 55 66   Whatsapp bevorzugt",
                "",
                "Ersatztermin bei Ausfall: Freitag 16 Uhr",
                "Raum 3, Eingang Hofseite",
            ],
        ),
        Document(
            doc_id="d06",
            variant="hand",
            correspondent="Zahnarztpraxis Dr. Lehner",
            document_type="Anmeldeformular",
            tags=["gesundheit"],
            title="Anmeldeformular Neupatient",
            created="2026-08-03",
            lines=[
                "Zahnarztpraxis Dr. Lehner",
                "Anmeldeformular Neupatient",
                "Eingang: 03.08.2026",
                "",
                "Versicherung: Grundversicherung",
                "Letzte Kontrolle: vor zwei Jahren",
                "Beschwerden: Empfindlichkeit oben rechts",
                "Seit wann: etwa drei Wochen",
                "Allergien: Penicillin",
                "Gewünschter Termin: vormittags",
            ],
        ),
        Document(
            doc_id="d07",
            variant="hand",
            correspondent="Kantonsspital Nordheim",
            document_type="Arztbericht",
            tags=["gesundheit"],
            title="Verlaufsnotiz Kontrolluntersuchung",
            created="2026-07-22",
            lines=[
                "Kantonsspital Nordheim",
                "Ambulanz Innere Medizin",
                "Verlaufsnotiz Kontrolluntersuchung",
                "Datum 22.07.2026",
                "",
                "Blutdruck 128 zu 82, Puls 68 regelmässig",
                "Laborwerte unauffällig",
                "Cholesterin leicht erhöht",
                "Beurteilung: Verlauf zufriedenstellend",
                "Kontrolle in sechs Monaten",
            ],
        ),
        Document(
            doc_id="d08",
            variant="hand",
            correspondent="Bibliothek Seefeld",
            document_type="Mahnung",
            tags=["freizeit", "finanzen"],
            title="Mahnung überfällige Medien",
            created="2026-06-30",
            lines=[
                "Bibliothek Seefeld",
                "Mahnung überfällige Medien",
                "Datum 30.06.2026",
                "",
                "Ausweisnummer 4471",
                "Drei Medien sind überfällig seit 12.06.2026",
                "Mahngebühr 6.00 CHF",
                "Zuschlag pro Woche 2.00 CHF",
                "Bitte innert zehn Tagen zurückbringen",
            ],
        ),
    ]


def _parse_truth(raw: str) -> tuple[dict[str, str], list[str]]:
    """Trennt den optionalen Metadatenkopf vom Referenztext.

    Format: ``schlüssel: wert`` je Zeile, dann ``---``, dann der Text. Fehlt der
    Kopf, ist die Datei reiner Referenztext und es wird nur das OCR gemessen.
    """
    if "\n---\n" not in raw:
        return {}, raw.strip().split("\n")
    head, _, body = raw.partition("\n---\n")
    meta: dict[str, str] = {}
    for line in head.strip().split("\n"):
        key, sep, value = line.partition(":")
        if sep:
            meta[key.strip()] = value.strip()
    return meta, body.strip().split("\n")


def _from_scan(truth: Path, index: int) -> Document | None:
    """Baut ein Dokument aus ``<name>.txt`` und, falls vorhanden, ``<name>.pdf``."""
    meta, lines = _parse_truth(truth.read_text(encoding="utf-8"))
    if not lines or not any(l.strip() for l in lines):
        return None
    pdf = truth.with_suffix(".pdf")
    scanned = pdf.exists()
    tags = [t.strip() for t in meta.get("tags", "").split(",") if t.strip()]
    classifiable = bool(meta.get("correspondent"))
    return Document(
        doc_id=truth.stem.split("-")[0] if classifiable else f"s{index:02d}",
        variant="hand" if classifiable else "scan",
        title=meta.get("title", truth.stem),
        lines=lines,
        correspondent=meta.get("correspondent"),
        document_type=meta.get("document_type"),
        tags=tags,
        created=meta.get("created"),
        source_pdf=str(pdf.relative_to(ROOT)) if scanned else None,
        handwriting="echt" if scanned else "font",
        notes=(
            "von Hand geschrieben und eingescannt"
            if scanned
            else "mit Handschrift-Font gerendert, kein echter Scan"
        ),
    )


def all_documents(include_font: bool = False) -> list[Document]:
    """Setzt den Korpus zusammen.

    Gedruckte Dokumente (``d01``–``d04``) stehen im Code — sie werden gerendert,
    niemand schreibt eine gedruckte Rechnung von Hand ab. Die handschriftlichen
    kommen vollständig aus ``ocr/``: je ein PDF mit einem ``.txt`` daneben, das
    den Referenztext und optional die Metadaten trägt.

    Der Referenztext liegt bewusst beim Scan und nicht im Code. Was auf dem
    Papier steht, entscheidet die Person mit dem Stift; eine zweite Fassung im
    Code liefe früher oder später auseinander, und die Fehlerrate würde gegen
    die falsche Vorlage gemessen.

    ``include_font`` rendert die handschriftlichen Texte zusätzlich mit einem
    Handschrift-Font. Nur für den Vergleich gedacht, wie viel leichter ein Font
    zu lesen ist als echte Handschrift.
    """
    docs = [d for d in _synthetic() if d.variant == "print"]
    if not SCAN_DIR.is_dir():
        return docs

    # Über die .txt-Dateien iterieren, nicht über die PDFs. Liegt kein Scan
    # daneben, wird der Text mit einem Handschrift-Font gerendert. Das Dokument
    # bleibt damit im Korpus, wird aber als "font" geführt und in der Auswertung
    # getrennt ausgewiesen — ein Font ist deutlich leichter zu lesen als echte
    # Handschrift, und beides in eine Zahl zu werfen würde das Ergebnis schönen.
    scans: list[Document] = []
    for truth in sorted(SCAN_DIR.glob("*.txt")):
        doc = _from_scan(truth, len(scans) + 1)
        if doc is not None:
            scans.append(doc)

    if include_font:
        for doc in list(scans):
            if doc.variant != "hand":
                continue
            twin = Document(**{**vars(doc), "doc_id": f"{doc.doc_id}f"})
            twin.source_pdf = None
            twin.handwriting = "font"
            twin.notes = "gleicher Text, mit Handschrift-Font gerendert"
            scans.append(twin)

    return docs + scans


# ---------------------------------------------------------------------------
# OCR-Simulation
# ---------------------------------------------------------------------------

def garble(text: str, seed: int) -> str:
    """Erzeugt den Zeichensalat, den klassisches OCR auf Handschrift produziert.

    Die Verstümmelung ahmt die typischen Fehlerklassen nach: Zeichen fallen aus,
    werden durch ähnlich aussehende ersetzt, Wörter zerfallen. Die gedruckten
    Kopfzeilen bleiben lesbar — genau daran erkennt man in der Praxis das halb
    erfasste Formular, dessen Labels stehen und dessen Inhalte fehlen.
    """
    rng = random.Random(seed)
    confusions = {
        "a": "o", "e": "c", "o": "0", "i": "l", "l": "1", "n": "rn",
        "u": "v", "s": "5", "t": "f", "g": "9", "h": "b", "m": "rri",
        "ä": "ö", "ö": "o", "ü": "ii", "ß": "b",
    }
    out: list[str] = []
    for idx, line in enumerate(text.split("\n")):
        if idx < 2 or not line.strip():
            out.append(line)  # Kopfzeilen sind gedruckt und bleiben lesbar
            continue
        chars: list[str] = []
        for ch in line:
            r = rng.random()
            if r < 0.22:
                continue  # Zeichen fällt aus
            if r < 0.45 and ch.lower() in confusions:
                chars.append(confusions[ch.lower()])
                continue
            if r < 0.50 and ch != " ":
                chars.append(rng.choice("\\|/~^*"))
                continue
            chars.append(ch)
        out.append("".join(chars))
    return "\n".join(out)


def ocr_text_for(doc: Document) -> str:
    """Der OCR-Text, den paperless liefern würde."""
    if doc.variant == "print":
        return doc.text
    return garble(doc.text, seed=abs(hash(doc.doc_id)) % 10_000)


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

def _paper(rng: random.Random) -> Image.Image:
    """Leicht fleckiges Papier statt reinem Weiss."""
    img = Image.new("L", (PAGE_W, PAGE_H), 247)
    px = img.load()
    assert px is not None
    for _ in range(PAGE_W * PAGE_H // 400):
        x = rng.randrange(PAGE_W)
        y = rng.randrange(PAGE_H)
        px[x, y] = max(0, px[x, y] - rng.randrange(6, 22))
    return img


def render(doc: Document, seed: int = 0) -> Path:
    """Rendert ein synthetisches Dokument als PNG."""
    CORPUS_DIR.mkdir(parents=True, exist_ok=True)
    rng = random.Random(seed + abs(hash(doc.doc_id)) % 10_000)

    handwritten = doc.variant == "hand"
    font = ImageFont.truetype(FONT_HAND if handwritten else FONT_PRINT, 40 if handwritten else 30)
    size = 40 if handwritten else 30

    img = _paper(rng)
    draw = ImageDraw.Draw(img)

    x0, y = 110, 130
    step = int(size * (1.72 if handwritten else 1.55))
    for line in doc.lines:
        if handwritten and line.strip():
            # Handschrift sitzt nicht auf der Grundlinie und variiert im Druck
            draw.text(
                (x0 + rng.randint(-7, 7), y + rng.randint(-4, 4)),
                line,
                font=font,
                fill=rng.randint(20, 70),
            )
        else:
            draw.text((x0, y), line, font=font, fill=25)
        y += step

    if handwritten:
        img = img.rotate(rng.uniform(-1.1, 1.1), resample=Image.BICUBIC, fillcolor=247)

    img.convert("RGB").save(doc.image_path, "PNG", optimize=True)
    return doc.image_path


def rasterize(doc: Document) -> Path:
    """Rendert die erste Seite eines gescannten PDF — gleiche dpi wie produktiv."""
    import pymupdf

    path = doc.image_path
    with pymupdf.open(ROOT / doc.source_pdf) as pdf:
        pdf[0].get_pixmap(dpi=SCAN_DPI).save(path)
    return path


def build(seed: int = 0, include_font: bool = False) -> list[Document]:
    """Erzeugt alle Seitenbilder und schreibt die Ground Truth als JSON."""
    CORPUS_DIR.mkdir(parents=True, exist_ok=True)
    docs = all_documents(include_font=include_font)
    for doc in docs:
        if doc.source_pdf is not None:
            rasterize(doc)
        else:
            render(doc, seed=seed)
    (CORPUS_DIR / "ground_truth.json").write_text(
        json.dumps([asdict(d) for d in docs], indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return docs


def normalize(text: str) -> str:
    """Vergleichsform: Unicode-Normalform, Kleinschreibung, Whitespace zusammengezogen."""
    return " ".join(unicodedata.normalize("NFKC", text).lower().split())


if __name__ == "__main__":
    built = build()
    print(f"{len(built)} Dokumente nach {CORPUS_DIR}")
    for d in built:
        print(f"  {d.doc_id} [{d.variant:5s}] {d.image_path.name}")
