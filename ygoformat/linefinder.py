"""Line finder jobs for the MCP server: resolve a starting hand and a deck, run the simulator's
wsl/line_finder.py in WSL in the background (a search takes minutes), and fetch its result.

Optional: needs a ygo-sim checkout (https://github.com/andrewboe/ygo-sim) with its WSL engine set up, named by
the YGOSIM_HOME environment variable. Jobs live in <data dir>/line_jobs/<id>/."""
from __future__ import annotations

import json
import os
import subprocess
import time
import uuid
from collections import Counter
from pathlib import Path

from . import decksave
from .api import DATA_DIR
from .formats import DeckInputError, parse_input, resolve

JOBS = DATA_DIR / "line_jobs"


def sim_home() -> Path:
    """The ygo-sim checkout named by YGOSIM_HOME; line search is unavailable without one."""
    home = os.environ.get("YGOSIM_HOME")
    if not home:
        raise DeckInputError("find_lines needs the ygo-sim simulator: set YGOSIM_HOME to a ygo-sim checkout with "
                             "its WSL engine set up (see docs/INSTALL.md, 'Optional: line search')")
    path = Path(home).expanduser()
    if not (path / "wsl" / "line_finder.py").is_file():
        raise DeckInputError(f"YGOSIM_HOME={home} has no wsl/line_finder.py; point it at a ygo-sim checkout")
    return path
DEPTH = {  # rollouts, generations, restarts, rough minutes (2026-10-20: 32x15x3 ~10 s, 48x60x8 ~2 min)
    "quick": (32, 15, 3, 1),
    "normal": (48, 40, 6, 1),
    "deep": (48, 60, 8, 2),
}


def to_wsl(path: Path) -> str:
    p = str(path.resolve()).replace("\\", "/")
    return f"/mnt/{p[0].lower()}{p[2:]}" if len(p) > 1 and p[1] == ":" else p


def _deck_input(con, ydk_path, ydk_text, decklist, saved_deck):
    if saved_deck is not None:
        if any(x is not None for x in (ydk_path, ydk_text, decklist)):
            raise DeckInputError("pass exactly one of saved_deck, ydk_path, ydk_text, decklist")
        decks = decksave.saved_decks(con)["decks"]
        hit = [d for d in decks if d["name"].lower() == saved_deck.lower()]
        if not hit:
            raise DeckInputError(f"no saved deck named {saved_deck!r}; saved: {[d['name'] for d in decks]}")
        ydk_path = hit[0]["ydk"]
    return parse_input(con, ydk_path, ydk_text, decklist)


def start(con, hand: list[str], ydk_path: str | None = None, ydk_text: str | None = None,
          decklist: dict | None = None, saved_deck: str | None = None, depth: str = "normal",
          executor: str | None = None) -> dict:
    sim = sim_home()
    deck = _deck_input(con, ydk_path, ydk_text, decklist, saved_deck)
    if deck.errors:
        raise DeckInputError("deck input errors: " + "; ".join(deck.errors))
    codes, errors = [], []
    for entry in hand:
        pid, note = resolve(con, str(entry))
        if pid is None:
            errors.append(note)
        else:
            codes.append(pid)
    if errors:
        raise DeckInputError("hand: " + "; ".join(errors))
    if len(codes) != 5:
        raise DeckInputError(f"a going-first hand has 5 cards, got {len(codes)}")
    have, need = Counter(deck.zones["main"]), Counter(codes)
    short = [c for c, k in need.items() if have[c] < k]
    if short:
        raise DeckInputError("hand cards not in the Main Deck (or more copies than it runs): " +
                             ", ".join(str(c) for c in short))
    if depth not in DEPTH:
        raise DeckInputError(f"depth must be one of {sorted(DEPTH)}")
    k, g, r, minutes = DEPTH[depth]
    job = time.strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:6]
    folder = JOBS / job
    folder.mkdir(parents=True)
    request = {"main": deck.zones["main"], "extra": deck.zones["extra"], "hand": codes,
               "rollouts": k, "generations": g, "restarts": r, "executor": executor}
    (folder / "request.json").write_text(json.dumps(request))
    log = open(folder / "log.txt", "w")
    flags = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NO_WINDOW", 0)
    subprocess.Popen(["wsl.exe", "-e", "bash", to_wsl(sim / "wsl" / "run_py.sh"), "line_finder.py",
                      to_wsl(folder / "request.json"), to_wsl(folder / "result.json")],
                     stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, creationflags=flags)
    meta = {"job_id": job, "started_at": time.time(), "depth": depth, "estimate_minutes": minutes,
            "hand": codes}
    (folder / "meta.json").write_text(json.dumps(meta))
    return {"job_id": job, "status": "running", "estimate_minutes": minutes,
            "note": "call line_result with this job_id; the search runs in the background"}


def result(con, job_id: str) -> dict:
    folder = JOBS / job_id
    if not folder.is_dir():
        raise DeckInputError(f"no line search job {job_id!r}")
    meta = json.loads((folder / "meta.json").read_text())
    out = folder / "result.json"
    elapsed = round((time.time() - meta["started_at"]) / 60, 1)
    if out.exists():
        res = json.loads(out.read_text())
        return {"job_id": job_id, "status": "done" if res.get("ok") else "failed", **res}
    if elapsed > 3 * meta["estimate_minutes"] + 10:
        tail = (folder / "log.txt").read_text(errors="replace")[-1500:] if (folder / "log.txt").exists() else ""
        return {"job_id": job_id, "status": "failed", "error": "no result after a long time", "log_tail": tail}
    return {"job_id": job_id, "status": "running", "elapsed_minutes": elapsed,
            "estimate_minutes": meta["estimate_minutes"]}
