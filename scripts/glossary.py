"""Tarea 1, fase 2.4: transcripción sin glosario contra con glosario, con IC por remuestreo de clips.

  python scripts/glossary.py

Usa la config de asr.glossary.run. "sin" es la transcripción ya cacheada del benchmark; "hotwords" e
"initial_prompt" se transcriben y cachean con sufijo (cache/transcripts/entrevistas/*__hotwords.json).
Además del WER mide el acierto de los términos del glosario que aparecen en la referencia, que es lo
que el glosario debería mejorar. Escribe results/glossary.csv y results/glossary_summary.csv.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd

from engine.asr import cache_path, load_cached, save_cached, transcribe
from engine.config import load_config, resolve
from engine.metrics import bootstrap_ci, normalize_text, wer_cer

AUDIO_EXT = {".wav", ".m4a", ".mp3", ".ogg", ".flac"}


def term_hits(reference: str, hypothesis: str, terms: list[str]) -> tuple[int, int]:
    """(términos del glosario dichos en la referencia, cuántos de ellos aparecen en la transcripción)."""
    ref, hyp = f" {normalize_text(reference)} ", f" {normalize_text(hypothesis)} "
    said = [t for t in terms if f" {t} " in ref]
    return len(said), sum(f" {t} " in hyp for t in said)


def main():
    cfg = load_config()
    asr, g = cfg["asr"], cfg["asr"]["glossary"]
    run, boot = g["run"], cfg["metrics"]["bootstrap"]
    terms = [normalize_text(t) for t in g["hotwords"].split(",")]
    variants = {"sin": {}, "hotwords": {"hotwords": g["hotwords"]}, "initial_prompt": {"initial_prompt": g["initial_prompt"]}}

    audio_dir = resolve(cfg["paths"]["audio_raw"]) / "entrevistas"
    cache_dir = resolve(cfg["paths"]["cache"]) / "entrevistas"
    refs_dir = resolve(cfg["paths"]["references"])
    stems = sorted(p.stem for p in refs_dir.glob("entrevista_*.txt"))

    rows = []
    for stem in stems:
        reference = (refs_dir / f"{stem}.txt").read_text(encoding="utf-8")
        for name, kwargs in variants.items():
            path = cache_path(cache_dir, stem, run["model"], run["device"], run["compute_type"],
                              None if name == "sin" else name)
            result = load_cached(path)
            if result is None:
                audio = next((p for p in audio_dir.glob(f"{stem}.*") if p.suffix.lower() in AUDIO_EXT), None)
                if audio is None:
                    print(f"[aviso] sin audio ni cache para {stem} / {name}")
                    continue
                print(f"[asr] {stem} {name}", flush=True)
                result = transcribe(audio, run["model"], run["device"], run["compute_type"],
                                    asr["language"], asr["beam_size"], **kwargs)
                save_cached(path, result)
            said, heard = term_hits(reference, result["text"], terms)
            rows.append({"audio": stem, "variante": name, "terminos_dichos": said, "terminos_oidos": heard,
                         **wer_cer(reference, result["text"], cfg["metrics"]["normalize_numbers"])})

    df = pd.DataFrame(rows)
    out_dir = resolve(cfg["paths"]["results"])
    df.to_csv(out_dir / "glossary.csv", index=False)

    # Diferencia pareada por clip (variante - sin): negativo en WER = el glosario ayudó
    base = df[df.variante == "sin"].set_index("audio")
    summary = []
    for name in variants:
        v = df[df.variante == name].set_index("audio")
        common = v.index.intersection(base.index)
        wer, lo, hi = bootstrap_ci(v.loc[common, "wer"], **boot)
        d, dlo, dhi = bootstrap_ci((v.loc[common, "wer"] - base.loc[common, "wer"]), **boot)
        summary.append({"variante": name, "clips": len(common), "wer": wer, "wer_ic_bajo": lo, "wer_ic_alto": hi,
                        "dif_wer_vs_sin": d, "dif_ic_bajo": dlo, "dif_ic_alto": dhi,
                        "terminos_oidos": int(v.loc[common, "terminos_oidos"].sum()),
                        "terminos_dichos": int(v.loc[common, "terminos_dichos"].sum())})
    summary = pd.DataFrame(summary)
    summary.to_csv(out_dir / "glossary_summary.csv", index=False)
    print(summary.round(4).to_string(index=False))


if __name__ == "__main__":
    main()
