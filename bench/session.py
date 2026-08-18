"""Neustart der Ollama-Session zwischen zwei Modellen.

Der Grund steht in den Messdaten: in einem früheren Vier-Modell-Lauf stiegen
die Zeiten desselben Modells auf gleichartigen Dokumenten von 345 s auf 2316 s,
und nach einem Neustart von Ollama lag dasselbe Modell auf demselben Dokument
wieder bei einem Fünftel der Zeit. Wer mehrere Modelle nacheinander in derselben
Session misst, misst also teilweise die Session statt die Modelle — und der
Fehler ist heimtückisch, weil das Ergebnis plausibel aussieht: das langsamere
Modell läuft später und wirkt dadurch noch langsamer.

Deshalb bekommt jedes Modell eine frische Session. Der Neustart ist ein
Kommando, kein fester Ablauf: lokal wird ``ollama serve`` beendet und neu
gestartet, auf einem Server wäre es ein ``ssh host systemctl restart ollama``.
Was der Runner in beiden Fällen selbst tut, ist warten, bis der Endpunkt wieder
antwortet, und protokollieren, wie alt die Session zum Messzeitpunkt war.
"""

from __future__ import annotations

import os
import subprocess
import time

import requests

from bench import telemetry

# Beendet den laufenden Server und startet ihn los von diesem Prozess neu, damit
# er das Ende des Benchmarks überlebt und der nächste Lauf ihn wiederfindet.
DEFAULT_RESTART_CMD = (
    "pkill -f 'ollama serve' || true; sleep 3; "
    "nohup ollama serve >> \"${TMPDIR:-/tmp}/ollama-serve.log\" 2>&1 &"
)


def healthy(base_url: str, timeout: float = 5.0) -> bool:
    try:
        return requests.get(f"{base_url}/api/tags", timeout=timeout).ok
    except Exception:
        return False


def wait_until_healthy(base_url: str, deadline_s: float = 120.0) -> bool:
    started = time.perf_counter()
    while time.perf_counter() - started < deadline_s:
        if healthy(base_url):
            return True
        time.sleep(2)
    return False


def uptime_s(base_url: str) -> int | None:
    """Laufzeit der Ollama-Session in Sekunden, lokal über den Serverprozess.

    Bei entferntem Ollama nicht ermittelbar — dann steht im Ergebnis ``None``
    statt einer Zahl, die den falschen Rechner beschreibt.
    """
    if not telemetry.is_local(base_url):
        return None
    return telemetry.process_stats("ollama serve")["uptime_s"]


def restart(base_url: str, cmd: str | None = None) -> dict:
    """Startet Ollama neu und wartet, bis der Endpunkt wieder antwortet."""
    command = cmd or DEFAULT_RESTART_CMD
    before = uptime_s(base_url)
    started = time.perf_counter()
    proc = subprocess.run(
        command, shell=True, capture_output=True, text=True,
        # Ohne eigene Sitzung stirbt der neue Serverprozess mit der Shell, die
        # ihn gestartet hat, sobald der Benchmark endet.
        start_new_session=True, env={**os.environ},
    )
    ok = wait_until_healthy(base_url)
    return {
        "restarted": ok,
        "command": command,
        "wait_s": round(time.perf_counter() - started, 1),
        "uptime_before_s": before,
        "uptime_after_s": uptime_s(base_url),
        "returncode": proc.returncode,
        "stderr": (proc.stderr or "").strip()[:400] or None,
    }
