"""WI-022: Config file persistence.

Saves and loads user settings (mask, length strategy, consistent pseudonymization,
custom regex patterns) to a JSON file in the user's home directory.
"""

from __future__ import annotations

import json
from pathlib import Path

CONFIG_DIR = Path.home() / ".hl7-anonymizer"
CONFIG_PATH = CONFIG_DIR / "settings.json"

DEFAULT_CONFIG = {
    "mask": "***",
    "length_preserve": False,
    "consistent": False,
    "custom_regex_patterns": [],
}


def load_config() -> dict:
    """Load config from file, returning defaults for missing keys."""
    config = dict(DEFAULT_CONFIG)
    if CONFIG_PATH.exists():
        try:
            data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                config.update(data)
        except (json.JSONDecodeError, OSError):
            pass
    return config


def save_config(config: dict):
    """Save config to file."""
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        CONFIG_PATH.write_text(
            json.dumps(config, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    except OSError:
        pass
