"""Reset the working database to the original shop values.

    .venv/bin/python backend/reset_db.py

Copies data/campus_customs.db (the original, never modified) over data/campus_customs_new.db.
The previous working copy is kept in data/backups/ first, so a reset is never a loss.
run_team.py calls this automatically before every full run.
"""

from __future__ import annotations

import hashlib
import shutil
from datetime import datetime
from pathlib import Path

HW = Path(__file__).resolve().parent.parent
ORIGINAL_DB = HW / "data" / "campus_customs.db"
WORKING_DB = HW / "data" / "campus_customs_new.db"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def reset(working: Path = WORKING_DB) -> dict[str, str | None]:
    working = working.resolve()
    if working == ORIGINAL_DB.resolve():
        raise SystemExit("The working copy cannot be the original database")
    original_hash = sha256(ORIGINAL_DB)
    backup = None
    if working.exists() and sha256(working) != original_hash:
        backups = working.parent / "backups"  # next to the file being reset (data/backups for the real copy)
        backups.mkdir(parents=True, exist_ok=True)
        backup = backups / f"{working.stem}.{datetime.now():%Y%m%d-%H%M%S}.db"
        shutil.copy2(working, backup)
    working.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ORIGINAL_DB, working)
    if sha256(working) != original_hash or sha256(ORIGINAL_DB) != original_hash:
        raise SystemExit("Reset verification failed")
    return {"working_copy": str(working), "backup_of_previous": str(backup) if backup else None,
            "sha256": original_hash}


if __name__ == "__main__":
    print(reset())
