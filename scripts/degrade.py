"""Construye la escalera L0-L3 a partir de data/audio/llamadas/*.

  python scripts/degrade.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import soundfile as sf

from engine.config import load_config, resolve
from engine.degrade import build_ladder, measured_snr_db, to_wav

AUDIO_EXT = {".wav", ".m4a", ".mp3", ".ogg", ".flac"}


def main():
    cfg = load_config()
    src_dir = resolve(cfg["paths"]["audio_raw"]) / "llamadas"
    out_dir = resolve(cfg["paths"]["audio_degraded"])
    levels = cfg["degradation"]["levels"]
    sr = cfg["degradation"]["sample_rate"]

    rows = []
    for src in sorted(p for p in src_dir.glob("*") if p.suffix.lower() in AUDIO_EXT):
        wav = to_wav(src, out_dir / "_tmp" / f"{src.stem}.wav", sr)
        paths = build_ladder(wav, out_dir, levels)
        clean, _ = sf.read(paths["L0"], dtype="float32")
        prev = clean
        for name, path in paths.items():
            audio, _ = sf.read(path, dtype="float32")
            first = name == "L0"
            # vs. L0: degradación acumulada; vs. nivel anterior: lo que agrega este paso (en L3, el SNR del ruido)
            rows.append({"audio": src.stem, "level": name,
                         "snr_vs_L0_db": None if first else measured_snr_db(clean, audio),
                         "snr_vs_anterior_db": None if first else measured_snr_db(prev, audio)})
            prev = audio
        print(f"[ok] {src.name} -> {', '.join(paths)}")

    out = resolve(cfg["paths"]["results"]) / "degradation.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(out, index=False)
    print(f"[ok] SNR medido -> {out}")


if __name__ == "__main__":
    main()
