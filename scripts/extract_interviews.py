"""Tarea 1: extracción por reglas y por LLM, verificación literal y comparación con el ground truth.

  python scripts/extract_interviews.py            # reglas + LLM
  python scripts/extract_interviews.py --no-llm   # solo reglas (sin API key)
"""
import argparse
import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd

from engine import extract_rules
from engine.asr import cache_path, load_cached
from engine.config import load_config, resolve
from engine.metrics import normalize_text
from engine.verify import verify_fields


def matches(predicted, expected) -> bool:
    if expected is None:
        return predicted in (None, [], "")
    if isinstance(expected, list):
        return {normalize_text(str(x)) for x in predicted or []} == {normalize_text(str(x)) for x in expected}
    return predicted is not None and normalize_text(str(predicted)) == normalize_text(str(expected))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-llm", action="store_true")
    args = parser.parse_args()

    cfg = load_config()
    d = cfg["asr"]["default"]
    gt = json.loads((resolve(cfg["paths"]["ground_truth"]) / "entrevistas.json").read_text(encoding="utf-8"))
    cache_dir = resolve(cfg["paths"]["cache"]) / "entrevistas"

    methods = {"reglas": lambda t, ref: extract_rules.extract(t, cfg["extraction"]["technologies"], ref)}
    if not args.no_llm:
        from engine.extract_llm import extract_interview
        methods["llm"] = lambda t, ref: extract_interview(t, cfg["extraction"]["llm"], ref)

    rows, details = [], {}
    for audio_id, expected in gt.items():
        if audio_id.startswith("_"):
            continue
        cached = load_cached(cache_path(cache_dir, audio_id, d["model"], d["device"], d["compute_type"]))
        if cached is None:
            print(f"[aviso] sin transcripción cacheada para {audio_id}; corre scripts/transcribe.py")
            continue
        transcript = cached["text"]
        ref = date.fromisoformat(expected["fecha_entrevista"])
        details[audio_id] = {}
        for method, fn in methods.items():
            predicted = fn(transcript, ref)
            # La frase de disponibilidad se verifica literal; la fecha es lo que se compara
            verified = verify_fields({f: predicted.get(f) for f in cfg["extraction"]["fields"]}, transcript)
            verified["disponibilidad"]["fecha"] = predicted.get("disponibilidad_fecha")
            details[audio_id][method] = verified
            for field in cfg["extraction"]["fields"]:
                v = verified[field]
                value = v["fecha"] if field == "disponibilidad" else v["valor"]
                rows.append({
                    "audio": audio_id, "metodo": method, "campo": field,
                    "valor": json.dumps(value, ensure_ascii=False),
                    "esperado": json.dumps(expected.get(field), ensure_ascii=False),
                    "estado": v["estado"],
                    "correcto": matches(value, expected.get(field)),
                })

    out_dir = resolve(cfg["paths"]["results"])
    out_dir.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(rows)
    df.to_csv(out_dir / "extraction.csv", index=False)
    (out_dir / "extraction.json").write_text(json.dumps(details, ensure_ascii=False, indent=2), encoding="utf-8")
    if not df.empty:
        print(df.groupby(["metodo", "campo"])["correcto"].mean().unstack(0).round(2))


if __name__ == "__main__":
    main()
