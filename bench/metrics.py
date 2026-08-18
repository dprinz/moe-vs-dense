"""Genauigkeitsmasse.

Vier Aufgaben, vier Masse — jeweils so gewählt, dass ein Punktabzug auch
wirklich einen inhaltlichen Fehler bedeutet und nicht eine Formulierungsfrage:

* OCR-Check    binär: hat das Modell den kaputten Text als kaputt erkannt?
* Vision-OCR   Zeichen- und Wortfehlerrate gegen den bekannten Volltext
* Klassifikation  exakter Treffer bei Korrespondent und Typ, F1 bei den Tags
* Metadaten    exakter Treffer beim Datum, Token-F1 beim Titel

Der Titel wird bewusst nicht exakt verglichen: "Stromabrechnung 2. Quartal 2026"
und "Stromabrechnung Q2 2026" sind beide brauchbar. Token-F1 bildet das ab,
ohne beliebige Formulierungen durchzuwinken.
"""

from __future__ import annotations

import re
import unicodedata


def _norm(text: str) -> str:
    text = unicodedata.normalize("NFKC", text or "").lower()
    text = text.replace("ß", "ss")
    for umlaut, plain in (("ä", "ae"), ("ö", "oe"), ("ü", "ue")):
        text = text.replace(umlaut, plain)
    return " ".join(text.split())


def _tokens(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", _norm(text))


def levenshtein(a: str, b: str) -> int:
    """Editierdistanz, iterativ mit zwei Zeilen (der Volltext ist zu lang für O(n*m) Speicher)."""
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def cer(reference: str, hypothesis: str) -> float:
    """Zeichenfehlerrate. 0.0 ist perfekt, 1.0 bedeutet komplett daneben."""
    ref, hyp = _norm(reference), _norm(hypothesis)
    if not ref:
        return 0.0 if not hyp else 1.0
    return min(1.0, levenshtein(ref, hyp) / len(ref))


def wer(reference: str, hypothesis: str) -> float:
    """Wortfehlerrate über normalisierte Tokens."""
    ref, hyp = _tokens(reference), _tokens(hypothesis)
    if not ref:
        return 0.0 if not hyp else 1.0
    # Levenshtein auf Wortebene: Tokens auf Zeichen abbilden, dann wiederverwenden
    vocab: dict[str, str] = {}

    def encode(seq: list[str]) -> str:
        out = []
        for tok in seq:
            if tok not in vocab:
                vocab[tok] = chr(0xE000 + len(vocab))
            out.append(vocab[tok])
        return "".join(out)

    return min(1.0, levenshtein(encode(ref), encode(hyp)) / len(ref))


def f1(expected: list[str], predicted: list[str]) -> float:
    """F1 über Mengen — für Tags und Titel-Tokens."""
    exp, pred = set(expected), set(predicted)
    if not exp and not pred:
        return 1.0
    if not exp or not pred:
        return 0.0
    tp = len(exp & pred)
    if tp == 0:
        return 0.0
    precision = tp / len(pred)
    recall = tp / len(exp)
    return 2 * precision * recall / (precision + recall)


def title_f1(expected: str, predicted: str) -> float:
    """Token-F1 des Titels, Stoppwörter raus."""
    # Auf normalisierten Tokens: _norm bildet "für" auf "fuer" ab, deshalb steht
    # es hier ohne Umlaut.
    stop = {"der", "die", "das", "und", "fuer", "von", "im", "am", "zur", "zum", "in"}
    exp = [t for t in _tokens(expected) if t not in stop]
    pred = [t for t in _tokens(predicted) if t not in stop]
    return f1(exp, pred)


def exact(expected: str | None, predicted: str | None) -> bool:
    return _norm(expected or "") == _norm(predicted or "") and bool(expected)


def mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0
