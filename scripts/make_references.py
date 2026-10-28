"""Genera data/references/<id>.txt a partir de docs/guiones/<id>.md.

Toma solo las líneas de diálogo (`**ROL:** texto`) y quita las etiquetas de hablante, para que la
referencia contenga exactamente lo que se dice en el audio.

  python scripts/make_references.py
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine.config import ROOT, load_config, resolve

LINE = re.compile(r"^\*\*[A-ZÁÉÍÓÚÑ]+:\*\*\s*(.+)$")


def dialogue(guion: Path) -> str:
    lines = guion.read_text(encoding="utf-8").splitlines()
    return " ".join(m.group(1).strip() for line in lines if (m := LINE.match(line.strip())))


def main():
    cfg = load_config()
    out_dir = resolve(cfg["paths"]["references"])
    out_dir.mkdir(parents=True, exist_ok=True)
    for guion in sorted((ROOT / "docs" / "guiones").glob("*_0*.md")):
        text = dialogue(guion)
        (out_dir / f"{guion.stem}.txt").write_text(text + "\n", encoding="utf-8")
        print(f"[ok] {guion.stem}: {len(text.split())} palabras")


if __name__ == "__main__":
    main()
