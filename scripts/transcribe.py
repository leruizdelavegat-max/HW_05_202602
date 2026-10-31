"""Transcribe y cachea. Genera results/benchmark_<set>.csv con WER, CER, tiempo y VRAM.

  python scripts/transcribe.py --set entrevistas            # grid completo (modelos × dispositivos × precisiones)
  python scripts/transcribe.py --set llamadas               # cada nivel L0-L3 con la config por defecto
  python scripts/transcribe.py --set llamadas --grid        # cada nivel con el grid completo
  python scripts/transcribe.py --set entrevistas --device cuda   # solo las combinaciones GPU (Colab)

Las combinaciones cuda se saltan si no hay GPU (córrelas en Colab y sube el cache).
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import ctranslate2
import pandas as pd

from engine.asr import cache_path, load_cached, save_cached, transcribe
from engine.config import load_config, resolve
from engine.metrics import wer_cer

AUDIO_EXT = {".wav", ".m4a", ".mp3", ".ogg", ".flac"}


def audio_jobs(cfg: dict, dataset: str) -> list[tuple[str, Path, Path]]:
    """Lista de (nivel, carpeta_audio, carpeta_cache)."""
    cache = resolve(cfg["paths"]["cache"]) / dataset
    if dataset == "entrevistas":
        return [("-", resolve(cfg["paths"]["audio_raw"]) / dataset, cache)]
    base = resolve(cfg["paths"]["audio_degraded"])
    return [(lvl, base / lvl, cache / lvl) for lvl in cfg["degradation"]["levels"]]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--set", choices=["entrevistas", "llamadas"], required=True)
    parser.add_argument("--grid", action="store_true", help="usar el grid completo también en llamadas")
    parser.add_argument("--device", choices=["cpu", "cuda"], help="correr solo las combinaciones de este dispositivo")
    parser.add_argument("--models", nargs="+", help="correr solo estos tamaños (p. ej. small)")
    args = parser.parse_args()

    cfg = load_config()
    asr = cfg["asr"]
    has_gpu = ctranslate2.get_cuda_device_count() > 0
    use_grid = args.set == "entrevistas" or args.grid
    combos = (
        [(m, r["device"], r["compute_type"]) for m in asr["models"] for r in asr["runs"]]
        if use_grid
        else [(asr["default"]["model"], asr["default"]["device"], asr["default"]["compute_type"])]
    )
    if args.device:
        combos = [c for c in combos if c[1] == args.device]
    if args.models:
        combos = [c for c in combos if c[0] in args.models]
    refs_dir = resolve(cfg["paths"]["references"])

    rows = []
    for level, audio_dir, cache_dir in audio_jobs(cfg, args.set):
        audios = sorted(p for p in audio_dir.glob("*") if p.suffix.lower() in AUDIO_EXT)
        if not audios:
            print(f"[aviso] no hay audios en {audio_dir}")
        for audio in audios:
            for size, device, ctype in combos:
                path = cache_path(cache_dir, audio.stem, size, device, ctype)
                result = load_cached(path)
                if result is None:
                    if device == "cuda" and not has_gpu:
                        print(f"[salto] {audio.name} {size}/{device}/{ctype}: no hay GPU")
                        continue
                    print(f"[asr] {level} {audio.name} {size}/{device}/{ctype}")
                    result = transcribe(audio, size, device, ctype, asr["language"], asr["beam_size"])
                    save_cached(path, result)
                row = {k: v for k, v in result.items() if k not in ("text", "segments")}
                row["level"] = level
                row["entorno"] = "colab" if device == "cuda" else "local"
                ref = refs_dir / f"{audio.stem}.txt"
                if ref.exists():
                    row.update(wer_cer(ref.read_text(encoding="utf-8"), result["text"],
                                       cfg["metrics"]["normalize_numbers"]))
                rows.append(row)

    out = resolve(cfg["paths"]["results"]) / f"benchmark_{args.set}.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(out, index=False)
    print(f"[ok] {len(rows)} filas -> {out}")


if __name__ == "__main__":
    main()
