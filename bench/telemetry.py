"""Zustand des Messrechners, mitgeschrieben je Dokument.

Hintergrund ist ein Fehlschlag: in einem früheren Lauf stiegen die Zeiten eines
Modells auf gleichartigen Dokumenten monoton an, bis Ollama einen 500er lieferte.
Ob dahinter Speicherdruck, Swap oder thermische Drosselung stand, liess sich
nachträglich nicht mehr sagen — es lagen schlicht keine Daten neben den Zeiten.

Deshalb wird jetzt zu jedem Dokument der Hostzustand mitgeschrieben. Die Werte
sind bewusst billig zu holen (Millisekunden gegen Sekunden bis Minuten Messzeit)
und werden nicht ausgewertet, sondern nur protokolliert: was die Degradation
auslöst, entscheidet die Auswertung hinterher, nicht dieses Modul.

Nur für eine lokale Ollama-Instanz. Läuft der Server auf einem anderen Host,
beschreiben die Zahlen den falschen Rechner — dann wird nichts erhoben.
"""

from __future__ import annotations

import os
import platform
import re
import shutil
import subprocess
import time
from urllib.parse import urlparse

LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1", "0.0.0.0"}


def is_local(base_url: str) -> bool:
    return (urlparse(base_url).hostname or "").lower() in LOCAL_HOSTS


def _run(cmd: list[str], timeout: float = 5.0) -> str:
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except Exception:
        return ""
    return out.stdout


# Der Prozess, der die Gewichte hält, heisst je nach Ollama-Version anders:
# ältere Versionen starten ``llama-server``, neuere einen eigenen
# ``ollama runner``. Beide Namen abfragen, sonst fehlt genau die Zahl, die eine
# Speicherdegradation zeigen würde — und zwar unauffällig als ``null``.
RUNNER_PATTERN = "llama-server|ollama runner"


def _pid(pattern: str) -> int | None:
    """PID des ersten Prozesses, dessen Kommandozeile auf ``pattern`` passt."""
    out = _run(["pgrep", "-f", pattern]).split()
    return int(out[0]) if out else None


def _ps(pid: int, fmt: str) -> str:
    return _run(["ps", "-o", fmt, "-p", str(pid)]).strip()


def _elapsed_s(etime: str) -> int | None:
    """Wandelt das ``ps``-Format ``[[dd-]hh:]mm:ss`` in Sekunden.

    macOS kennt kein ``etimes``, das die Sekunden direkt liefern würde — die
    formatierte Laufzeit ist alles, was ohne Zusatzwerkzeug zu haben ist.
    """
    if not etime:
        return None
    days, _, rest = etime.partition("-")
    if not rest:
        days, rest = "0", days
    parts = [int(p) for p in rest.split(":")] if rest.replace(":", "").isdigit() else []
    if not parts:
        return None
    while len(parts) < 3:
        parts.insert(0, 0)
    hours, minutes, seconds = parts[-3:]
    return int(days) * 86400 + hours * 3600 + minutes * 60 + seconds


def process_stats(pattern: str) -> dict:
    """Laufzeit und Speicherbelegung eines Prozesses, über sein Kommando gefunden."""
    pid = _pid(pattern)
    if pid is None:
        return {"pid": None, "uptime_s": None, "rss_gb": None}
    rss = _ps(pid, "rss=")
    return {
        "pid": pid,
        "uptime_s": _elapsed_s(_ps(pid, "etime=")),
        "rss_gb": round(int(rss) / 1024 / 1024, 2) if rss.isdigit() else None,
    }


def _memory() -> dict:
    """Freier Speicher und Swap-Nutzung aus vm_stat und sysctl.

    ``vm_stat`` statt ``memory_pressure``, weil es ohne Wartezeit antwortet und
    die Seitenzahlen direkt liefert. Frei gezählt werden freie und inaktive
    Seiten: inaktive sind unter Druck sofort verfügbar, sie als belegt zu führen
    würde den Speicherdruck dramatischer aussehen lassen, als er ist.
    """
    stats: dict = {"free_gb": None, "swap_used_mb": None, "compressed_gb": None}

    text = _run(["vm_stat"])
    if text:
        size = re.search(r"page size of (\d+) bytes", text)
        page = int(size.group(1)) if size else 4096
        pages = {
            key: int(value)
            for key, value in re.findall(r"^(.+?):\s+(\d+)\.", text, flags=re.MULTILINE)
        }
        free = pages.get("Pages free", 0) + pages.get("Pages inactive", 0)
        stats["free_gb"] = round(free * page / 1024**3, 2)
        occupied = pages.get("Pages occupied by compressor", 0)
        stats["compressed_gb"] = round(occupied * page / 1024**3, 2)

    swap = _run(["sysctl", "-n", "vm.swapusage"])
    used = re.search(r"used\s*=\s*([\d.]+)M", swap)
    if used:
        stats["swap_used_mb"] = float(used.group(1))
    return stats


def _thermal() -> dict:
    """Thermische Drosselung, soweit sie ohne erhöhte Rechte sichtbar ist.

    ``pmset -g therm`` meldet eine Begrenzung erst, wenn eine aufgetreten ist —
    solange nichts gedrosselt wird, steht dort nur, dass nichts vorliegt. Ein
    ``None`` heisst also "keine Drosselung protokolliert", nicht "unbekannt".
    Feinere Werte gäbe nur ``powermetrics``, und das verlangt sudo; ein
    Benchmark, der nach einem Passwort fragt, läuft nachts nicht durch.
    """
    text = _run(["pmset", "-g", "therm"])
    limit = re.search(r"CPU_Speed_Limit\s*=\s*(\d+)", text)
    return {
        "cpu_speed_limit": int(limit.group(1)) if limit else None,
        "warning_recorded": "No thermal warning level has been recorded" not in text,
    }


def sample(base_url: str) -> dict | None:
    """Momentaufnahme des Hosts, oder ``None`` bei entferntem Ollama."""
    if not is_local(base_url) or not shutil.which("vm_stat"):
        return None
    server = process_stats("ollama serve")
    runner = process_stats(RUNNER_PATTERN)
    return {
        "at": time.time(),
        "server_uptime_s": server["uptime_s"],
        "runner_uptime_s": runner["uptime_s"],
        "runner_rss_gb": runner["rss_gb"],
        "memory": _memory(),
        "thermal": _thermal(),
    }


def host_info() -> dict:
    """Beschreibung des Messrechners, für die Nachvollziehbarkeit des Laufs.

    Ohne diese Angabe lassen sich zwei Ergebnisdateien nicht mehr einordnen:
    Zahlen von zwei verschiedenen Rechnern sehen im JSON identisch aus, sind
    aber nur innerhalb eines Laufs vergleichbar.
    """
    ram = _run(["sysctl", "-n", "hw.memsize"]).strip()
    version = _run(["ollama", "--version"]).strip().splitlines()
    return {
        "platform": platform.platform(),
        "cpu": _run(["sysctl", "-n", "machdep.cpu.brand_string"]).strip() or platform.machine(),
        "cores": os.cpu_count(),
        "ram_gb": round(int(ram) / 1024**3) if ram.isdigit() else None,
        "ollama_version": next((v for v in version if "version" in v.lower()), None),
    }
