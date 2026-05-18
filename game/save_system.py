from __future__ import annotations

import json
from pathlib import Path

from .character import Character


SAVE_DIR = Path("saves")


def save_game(character: Character, slot_name: str = "autosave") -> Path:
    SAVE_DIR.mkdir(exist_ok=True)
    safe_name = "".join(ch for ch in slot_name if ch.isalnum() or ch in ("-", "_")).strip() or "save"
    path = SAVE_DIR / f"{safe_name}.json"
    path.write_text(json.dumps(character.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def load_game(slot_name: str = "autosave") -> Character:
    path = SAVE_DIR / f"{slot_name}.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    return Character.from_dict(data)


def list_saves() -> list[str]:
    SAVE_DIR.mkdir(exist_ok=True)
    return sorted(path.stem for path in SAVE_DIR.glob("*.json"))

