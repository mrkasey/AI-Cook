"""
Persist API key + profile to a JSON file in the user's home directory.
The file lives at ~/.meal_assistant/config.json and never leaves the device.
"""
from __future__ import annotations
import json
from pathlib import Path
from models import Profile

_CONFIG_DIR = Path.home() / ".meal_assistant"
_CONFIG_FILE = _CONFIG_DIR / "config.json"


def save_config(api_key: str, profile: Profile) -> None:
    _CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    _CONFIG_FILE.write_text(
        json.dumps({"api_key": api_key, "profile": profile.model_dump()}, indent=2),
        encoding="utf-8",
    )


def load_config() -> tuple[str | None, Profile | None]:
    if not _CONFIG_FILE.exists():
        return None, None
    try:
        data = json.loads(_CONFIG_FILE.read_text(encoding="utf-8"))
        api_key = data.get("api_key") or None
        profile = Profile(**data["profile"]) if "profile" in data else None
        return api_key, profile
    except Exception:
        return None, None


def clear_config() -> None:
    if _CONFIG_FILE.exists():
        _CONFIG_FILE.unlink()
