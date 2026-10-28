from pathlib import Path

import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent

load_dotenv(ROOT / ".env")


def load_config(path: Path = ROOT / "config.yaml") -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def resolve(relative: str) -> Path:
    """Ruta del config.yaml -> ruta absoluta dentro del repo."""
    return ROOT / relative
