"""User settings, stored outside the project so updates never overwrite them."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

SETTINGS_FILE = Path.home() / ".ytdown" / "settings.json"


def default_output_dir() -> str:
    return str(Path.home() / "Downloads" / "yt down")


@dataclass
class Settings:
    output_dir: str

    @classmethod
    def load(cls, path: Path = SETTINGS_FILE) -> Settings:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            output_dir = str(data["output_dir"])
        except (OSError, ValueError, KeyError, TypeError):
            output_dir = default_output_dir()
        return cls(output_dir=output_dir)

    def save(self, path: Path = SETTINGS_FILE) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")


def validate_output_dir(raw: str) -> Path:
    """Return a usable absolute folder, creating it if needed. Raises ValueError otherwise."""
    text = raw.strip()
    if not text:
        raise ValueError("Indica una cartella.")
    path = Path(text).expanduser()
    if not path.is_absolute():
        raise ValueError("Indica un percorso completo (assoluto).")
    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise ValueError(f"Impossibile usare questa cartella: {exc.strerror or exc}") from exc
    return path
