"""Punto de entrada único del motor: de un audio a un registro verificado.

    from engine.pipeline import process_audio
    result = process_audio("entrevista.m4a", kind="entrevista", method="llm")

Devuelve siempre un dict (nunca lanza): transcripción, campos, cuáles se verificaron,
dispositivo usado, tiempo transcurrido y el error si lo hubo. La app solo llama a esta función.
"""
import time
from datetime import date
from pathlib import Path

from engine import extract_rules
from engine.config import load_config
from engine.validate import check_total
from engine.verify import verify_fields


def _asr_settings(cfg: dict) -> tuple[str, str, str]:
    """La config por defecto pide cuda; sin GPU se usa CPU int8 (la combinación más rápida en CPU)."""
    import ctranslate2

    d = cfg["asr"]["default"]
    if d["device"] == "cuda" and ctranslate2.get_cuda_device_count() == 0:
        return d["model"], "cpu", "int8"
    return d["model"], d["device"], d["compute_type"]


def process_audio(audio_path: str | Path, kind: str = "entrevista", method: str = "llm",
                  ref_date: date | None = None, model: str | None = None) -> dict:
    """kind: "entrevista" | "llamada". method: "llm" | "reglas" (las llamadas solo usan LLM)."""
    cfg = load_config()
    ref_date = ref_date or date.today()
    t0 = time.perf_counter()
    result = {"audio": Path(audio_path).name, "kind": kind, "method": method, "transcript": None,
              "fields": None, "verified": None, "validation": None, "device": None,
              "compute_type": None, "transcribe_s": None, "elapsed_s": None, "error": None}
    try:
        from engine.asr import transcribe

        size, device, ctype = _asr_settings(cfg)
        asr = transcribe(Path(audio_path), model or size, device, ctype,
                         cfg["asr"]["language"], cfg["asr"]["beam_size"])
        text = asr["text"]
        result.update(transcript=text, device=asr["runtime_device"], compute_type=ctype,
                      transcribe_s=asr["transcribe_s"])

        if kind == "entrevista":
            if method == "llm":
                from engine.extract_llm import extract_interview

                fields = extract_interview(text, cfg["extraction"]["llm"], ref_date)
            else:
                fields = extract_rules.extract(text, cfg["extraction"]["technologies"], ref_date)
            verified = verify_fields({f: fields.get(f) for f in cfg["extraction"]["fields"]}, text)
            verified["disponibilidad"]["fecha"] = fields.get("disponibilidad_fecha")
        else:
            from engine.extract_llm import extract_order

            fields = extract_order(text, cfg["calls"]["domain"], cfg["extraction"]["llm"])
            verified = verify_fields({
                "productos": [i["producto"] for i in fields["items"]],
                "direccion_o_contrato": fields.get("direccion_o_contrato"),
                "metodo_pago": fields.get("metodo_pago"),
                "total_dicho": fields.get("total_dicho"),
            }, text)
            result["validation"] = check_total(fields, cfg["calls"]["total_tolerance"])
        result.update(fields=fields, verified=verified)
    except Exception as exc:  # el resultado lleva el error en vez de romper la app
        result["error"] = f"{type(exc).__name__}: {exc}"
    result["elapsed_s"] = time.perf_counter() - t0
    return result
