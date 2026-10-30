"""Compara cada referencia (guion) con lo que transcribieron dos modelos distintos.

La referencia para el WER debe ser lo que realmente se dijo, no el guion. Este reporte marca dónde
la transcripción se aparta del guion y separa dos casos:

  - [AMBOS]  los dos modelos coinciden entre sí y difieren del guion: probablemente quien habló se
             salió del texto. Hay que escucharlo en el minuto indicado.
  - [UNO]    solo un modelo difiere: probablemente es un error del ASR. El guion se deja como está.

  python scripts/diff_references.py --set entrevistas            # solo el reporte
  python scripts/diff_references.py --set entrevistas --apply    # además corrige las referencias
  python scripts/diff_references.py --set llamadas               # usa el nivel L0

Con --apply, cada referencia pasa a ser el guion con los tramos [AMBOS] reemplazados por lo que se
escuchó (texto normalizado, igual que lo compara el WER). Es un borrador: escucha cada tramo y anota
en data/references/revisiones.json si fue un error del ASR ("asr", no se aplica) o si se dijo así
("habla", se aplica aunque solo un modelo lo haya escuchado). Vuelve a correr con --apply.
Escribe results/diff_<set>.md.
"""
import argparse
import difflib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine.asr import cache_path, load_cached
from engine.config import load_config, resolve
from engine.metrics import normalize_text

PAIRS = [("medium", "cpu", "int8"), ("small", "cpu", "int8"),
         ("medium", "cuda", "float16"), ("small", "cuda", "float16")]


def timed_tokens(result: dict) -> tuple[list[str], list[float]]:
    """Palabras normalizadas de la transcripción con un tiempo aproximado (repartido en su segmento)."""
    words, times = [], []
    for seg in result["segments"]:
        toks = normalize_text(seg["text"]).split()
        step = (seg["end"] - seg["start"]) / max(len(toks), 1)
        words += toks
        times += [seg["start"] + k * step for k in range(len(toks))]
    return words, times


def opcodes(ref: list[str], hyp: list[str]):
    return [op for op in difflib.SequenceMatcher(a=ref, b=hyp, autojunk=False).get_opcodes() if op[0] != "equal"]


def mmss(seconds: float) -> str:
    return f"{int(seconds // 60)}:{int(seconds % 60):02d}"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--set", choices=["entrevistas", "llamadas"], required=True)
    parser.add_argument("--apply", action="store_true", help="reescribir las referencias con los tramos [AMBOS]")
    args = parser.parse_args()

    cfg = load_config()
    cache_dir = resolve(cfg["paths"]["cache"]) / args.set
    if args.set == "llamadas":
        cache_dir = cache_dir / "L0"
    refs_dir = resolve(cfg["paths"]["references"])
    reviews_file = refs_dir / "revisiones.json"
    reviews = json.loads(reviews_file.read_text(encoding="utf-8")) if reviews_file.exists() else {}
    out = [f"# Diferencias entre guion y audio · {args.set}\n",
           "Escucha cada tramo **[AMBOS]** en el minuto indicado. Si se dijo así, la referencia está bien; "
           "si el audio dice lo del guion, fue un error del ASR y hay que revertir ese tramo.\n"]

    for ref_path in sorted(refs_dir.glob(f"{args.set[:-1]}*_0*.txt")):
        stem = ref_path.stem
        found = [(f"{s}/{d}/{c}", r) for s, d, c in PAIRS
                 if (r := load_cached(cache_path(cache_dir, stem, s, d, c)))]
        if len(found) < 2:
            print(f"[aviso] {stem}: hacen falta dos transcripciones distintas")
            continue
        (name_a, a), (name_b, b) = found[:2]
        ref = normalize_text(ref_path.read_text(encoding="utf-8")).split()
        hyp_a, times_a = timed_tokens(a)
        hyp_b, _ = timed_tokens(b)
        dev_b = {(i1, i2): hyp_b[j1:j2] for _, i1, i2, j1, j2 in opcodes(ref, hyp_b)}

        decided = {(r["guion"], r["oido"]): r["decision"] for r in reviews.get(stem, [])}
        out.append(f"\n## {stem}\n\nModelos: `{name_a}` y `{name_b}`\n")
        corrected, last, n_both = [], 0, 0
        for _, i1, i2, j1, j2 in opcodes(ref, hyp_a):
            heard = hyp_a[j1:j2]
            both = dev_b.get((i1, i2)) == heard
            at = mmss(times_a[min(j1, len(times_a) - 1)]) if times_a else "?"
            context = " ".join(ref[max(0, i1 - 5):i1])
            decision = decided.get((" ".join(ref[i1:i2]), " ".join(heard)))
            tag = {"asr": "✔ error del ASR (escuchado)", "habla": "✔ se dijo así (escuchado)"}.get(
                decision, "**[AMBOS]**" if both else "[UNO]")
            out.append(f"- `{at}` {tag} …{context} **«{' '.join(ref[i1:i2]) or '∅'}»** → «{' '.join(heard) or '∅'}»")
            if decision == "habla" or (both and decision != "asr"):
                corrected += ref[last:i1] + heard
                last = i2
                n_both += 1
        corrected += ref[last:]
        print(f"[ok] {stem}: {len(opcodes(ref, hyp_a))} diferencias, {n_both} en ambos modelos")
        if args.apply:
            ref_path.write_text(" ".join(corrected) + "\n", encoding="utf-8")
            verified_file = refs_dir / "VERIFICADAS"
            verified = set(verified_file.read_text(encoding="utf-8").split()) if verified_file.exists() else set()
            verified_file.write_text("\n".join(sorted(verified | {stem})) + "\n", encoding="utf-8")
            print(f"     referencia corregida -> {ref_path.name}")

    dst = resolve(cfg["paths"]["results"]) / f"diff_{args.set}.md"
    dst.write_text("\n".join(out) + "\n", encoding="utf-8")
    print(f"[ok] -> {dst}")


if __name__ == "__main__":
    main()
