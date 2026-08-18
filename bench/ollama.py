"""Dünner Ollama-Client mit Zeitmessung.

Bewusst die rohe HTTP-API statt LlamaIndex, obwohl das produktive Script
LlamaIndex benutzt: nur ``/api/generate`` liefert ``eval_count`` und
``eval_duration`` und damit eine Token-Rate, die unabhängig von Prompt-Länge
und Ladezeit ist. Über einen Framework-Wrapper gemessen wäre die Zahl eine
Mischung aus Modell und Wrapper-Overhead.

Die Prompts sind dieselben, s. :mod:`bench.prompts`. Gemessen wird also die
Modellleistung auf der echten Aufgabe, nur ohne die Zwischenschicht.
"""

from __future__ import annotations

import base64
import json
import re
import time
from dataclasses import dataclass, field
from pathlib import Path

import requests


@dataclass
class Response:
    """Antwort samt allem, was für die Auswertung gebraucht wird."""

    text: str
    wall_s: float
    prompt_tokens: int
    eval_tokens: int
    eval_s: float
    load_s: float
    error: str | None = None

    @property
    def tokens_per_s(self) -> float:
        """Generierungsrate ohne Lade- und Prompt-Verarbeitungszeit."""
        return self.eval_tokens / self.eval_s if self.eval_s > 0 else 0.0

    def as_dict(self) -> dict:
        return {
            "wall_s": round(self.wall_s, 3),
            "prompt_tokens": self.prompt_tokens,
            "eval_tokens": self.eval_tokens,
            "eval_s": round(self.eval_s, 3),
            "load_s": round(self.load_s, 3),
            "tokens_per_s": round(self.tokens_per_s, 2),
            "error": self.error,
        }


@dataclass
class Client:
    base_url: str
    model: str
    timeout: int = 1800
    keep_alive: str = "30m"
    temperature: float = 0.1
    _session: requests.Session = field(default_factory=requests.Session, repr=False)

    def generate(self, prompt: str, image: Path | None = None) -> Response:
        payload: dict = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "keep_alive": self.keep_alive,
            "options": {"temperature": self.temperature},
        }
        if image is not None:
            payload["images"] = [base64.b64encode(image.read_bytes()).decode()]

        started = time.perf_counter()
        try:
            r = self._session.post(
                f"{self.base_url}/api/generate", json=payload, timeout=self.timeout
            )
            r.raise_for_status()
            data = r.json()
        except Exception as exc:  # Netzfehler, Timeout, 500 vom Runner
            return Response(
                text="",
                wall_s=time.perf_counter() - started,
                prompt_tokens=0,
                eval_tokens=0,
                eval_s=0.0,
                load_s=0.0,
                error=f"{type(exc).__name__}: {exc}",
            )

        return Response(
            text=data.get("response", ""),
            wall_s=time.perf_counter() - started,
            prompt_tokens=int(data.get("prompt_eval_count") or 0),
            eval_tokens=int(data.get("eval_count") or 0),
            eval_s=(data.get("eval_duration") or 0) / 1e9,
            load_s=(data.get("load_duration") or 0) / 1e9,
        )

    def warmup(self) -> Response:
        """Lädt das Modell, damit die erste Messung nicht die Ladezeit enthält."""
        return self.generate("Antworte nur mit: ok")

    def unload(self) -> None:
        """Gibt den Speicher frei, damit das andere Modell nicht daneben liegt."""
        try:
            self._session.post(
                f"{self.base_url}/api/generate",
                json={"model": self.model, "prompt": "", "keep_alive": 0},
                timeout=60,
            )
        except Exception:
            pass


def info(base_url: str, model: str) -> dict:
    """Modellmetadaten für den Ergebnisbericht."""
    try:
        r = requests.post(f"{base_url}/api/show", json={"model": model}, timeout=60)
        r.raise_for_status()
        d = r.json().get("details", {})
        return {
            "family": d.get("family"),
            "parameter_size": d.get("parameter_size"),
            "quantization": d.get("quantization_level"),
            "capabilities": r.json().get("capabilities", []),
        }
    except Exception as exc:
        return {"error": f"{type(exc).__name__}: {exc}"}


def extract_json(text: str) -> dict:
    """Zieht das erste JSON-Objekt aus einer LLM-Antwort.

    Identisch zur Fassung im Windmill-Script: dass ein Modell sein JSON in Prosa
    oder Code-Fences verpackt, ist kein Fehler des Modells, sondern Alltag —
    und soll deshalb nicht als Genauigkeitsverlust zählen. Reasoning-Modelle
    liefern zusätzlich einen <think>-Block, der vorher weg muss.
    """
    cleaned = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    cleaned = re.sub(r"```(?:json)?", "", cleaned)
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError(f"kein JSON-Objekt in Antwort: {text[:200]}")
    return json.loads(cleaned[start : end + 1])


def strip_think(text: str) -> str:
    """Entfernt den Reasoning-Block aus einer Freitextantwort (Vision-OCR)."""
    return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
