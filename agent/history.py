"""Track past tweet drafts so the agent doesn't repeat itself."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

HISTORY_PATH = Path(__file__).parent.parent / "drafts" / "history.json"


def load() -> list[dict]:
    if not HISTORY_PATH.exists():
        return []
    return json.loads(HISTORY_PATH.read_text())


def append(entry: dict) -> None:
    HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    items = load()
    items.append(entry)
    HISTORY_PATH.write_text(json.dumps(items, indent=2))


def recent(days: int = 30) -> list[dict]:
    """Drafts from the last N days — what we feed back to Claude to avoid repeats."""
    cutoff = datetime.now() - timedelta(days=days)
    return [
        e for e in load()
        if datetime.fromisoformat(e["date"]) >= cutoff
    ]
