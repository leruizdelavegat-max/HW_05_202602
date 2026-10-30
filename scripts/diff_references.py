"""Compara cada referencia (guion) con lo que transcribieron dos modelos distintos.

La referencia para el WER debe ser lo que realmente se dijo, no el guion. Este reporte marca dónde
la transcripción se aparta del guion y separa dos casos:

  - [AMBOS]  los dos modelos coinciden entre sí y difieren del guion: probablemente quien habló se
             salió del texto. Hay que escuchar ese tramo y, si es así, corregir el guion.
  - [UNO]    solo un modelo difiere: probablemente es un error del ASR. El guion se deja como está.

  python scripts/diff_references.py --set entrevistas
  python scripts/diff_references.py --set llamadas        # usa el nivel L0

Escribe results/diff_<set>.md para revisar escuchando el audio.
"""
import argparse
import difflib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine.asr import cache_path, load_cached
from engine.config import load_config, resolve
from engine.metrics import normalize_text

PAIRS = [("medium", "cpu", "int8"), ("small", "cpu", "int8"),
         ("medium", "cuda", "float16"), ("small", "cuda", "float16")]


def deviations(ref: list[str], hyp: list[str]) -> list[tuple[int, int, str]]:
    """Tramos (inicio, fin) del guion que no coinciden, con lo que se transcribió en su lugar."""
    sm = difflib.SequenceMatcher(a=ref, b=hyp, autojunk=False)
    return [(i1, i2, " ".join(hyp[j1:j2])) for op, i1, i2, j1, j2 in sm.get_opcodes() if op != "equal"]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--set", choices=["entrevistas", "llamadas"], required=True)
    args = parser.parse_args()

    cfg = load_config()
    cache_dir = resolve(cfg["paths"]["cache"]) / args.set
    if args.set == "llamadas":
        cache_dir = cache_dir / "L0"
    out = [f"# Diferencias entre guion y audio · {args.set}\n"]

    for ref_path in sorted(resolve(cfg["paths"]["references"]).glob(f"{args.set[:-1]}*_0*.txt")):
        stem = ref_path.stem
        found = [(f"{s}/{d}/{c}", r) for s, d, c in PAIRS
                 if (r := load_cached(cache_path(cache_dir, stem, s, d, c)))]
        if len(found) < 2:
            print(f"[aviso] {stem}: hacen falta dos transcripciones distintas")
            continue
        (name_a, a), (name_b, b) = found[:2]
        ref = normalize_text(ref_path.read_text(encoding="utf-8")).split()
        dev_a = {(i1, i2): t for i1, i2, t in deviations(ref, normalize_text(a["text"]).split())}
        dev_b = {(i1, i2): t for i1, i2, t in deviations(ref, normalize_text(b["text"]).split())}

        out.append(f"\n## {stem}\n\nModelos: `{name_a}` y `{name_b}`\n")
        for (i1, i2), text_a in sorted(dev_a.items()):
            both = dev_b.get((i1, i2)) == text_a
            context = " ".join(ref[max(0, i1 - 5):i1])
            said = " ".join(ref[i1:i2]) or "∅"
            tag = "**[AMBOS]**" if both else "[UNO]"
            out.append(f"- {tag} …{context} **«{said}»** → «{text_a or '∅'}»")
        print(f"[ok] {stem}: {len(dev_a)} diferencias, {sum(dev_b.get(k) == v for k, v in dev_a.items())} en ambos modelos")

    dst = resolve(cfg["paths"]["results"]) / f"diff_{args.set}.md"
    dst.write_text("\n".join(out) + "\n", encoding="utf-8")
    print(f"[ok] -> {dst}")


if __name__ == "__main__":
    main()
