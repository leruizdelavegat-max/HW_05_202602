"""Intervalos de confianza y métricas del registro a partir de los resultados ya calculados (no transcribe).

  python scripts/report.py

Lee results/benchmark_*.csv, extraction.csv, calls_validation.csv y traps.csv, y escribe:
  asr_ci.csv          WER y CER medios con IC por remuestreo de clips (bootstrap)
  extraction_ci.csv   acierto por método y campo con IC de Wilson
  record_metrics.csv  F1 macro de nivel_ingles y error absoluto de los campos numéricos
  wer_vs_record.csv   WER del clip contra acierto del registro (¿predice el WER si el registro sirve?)
  calls_ci.csv        trampas detectadas y campos del pedido por nivel, con IC de Wilson
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd

from engine.config import load_config, resolve
from engine.metrics import bootstrap_ci, normalize_text, wilson_ci

NUMERIC = ["anios_experiencia", "pretension_salarial"]


def macro_f1(expected: list[str], predicted: list[str]) -> float:
    """F1 macro sobre las clases presentes en el ground truth (una predicción nula es un fallo)."""
    scores = []
    for c in sorted(set(expected)):
        tp = sum(e == c and p == c for e, p in zip(expected, predicted))
        fp = sum(e != c and p == c for e, p in zip(expected, predicted))
        fn = sum(e == c and p != c for e, p in zip(expected, predicted))
        scores.append(2 * tp / (2 * tp + fp + fn) if tp else 0.0)
    return sum(scores) / len(scores)


def ci_row(values, boot: dict, **keys) -> dict:
    m, lo, hi = bootstrap_ci(values, **boot)
    return {**keys, "media": m, "ic_bajo": lo, "ic_alto": hi}


def prop_row(hits: pd.Series, conf: float, **keys) -> dict:
    p, lo, hi = wilson_ci(int(hits.sum()), int(hits.size), conf)
    return {**keys, "aciertos": int(hits.sum()), "n": int(hits.size), "proporcion": p, "ic_bajo": lo, "ic_alto": hi}


def main():
    cfg = load_config()
    boot = cfg["metrics"]["bootstrap"]
    conf = boot["confidence"]
    d = cfg["asr"]["default"]
    res = resolve(cfg["paths"]["results"])

    # Capa 1: WER/CER con IC (5 clips por combinación: el IC es ancho y hay que decirlo)
    asr_rows = []
    bench_e = pd.read_csv(res / "benchmark_entrevistas.csv")
    for (model, device, ctype), g in bench_e.groupby(["model", "requested_device", "compute_type"]):
        for metric in ("wer", "cer"):
            asr_rows.append(ci_row(g[metric], boot, set="entrevistas", config=f"{model}/{device}/{ctype}", metrica=metric))
    bench_l = pd.read_csv(res / "benchmark_llamadas.csv")
    for level, g in bench_l.groupby("level"):
        for metric in ("wer", "cer"):
            asr_rows.append(ci_row(g[metric], boot, set="llamadas", config=level, metrica=metric))
    pd.DataFrame(asr_rows).to_csv(res / "asr_ci.csv", index=False)

    # Capa 2: acierto por campo con IC de Wilson
    ext = pd.read_csv(res / "extraction.csv", dtype={"valor": str, "esperado": str}, keep_default_na=False)
    ext_rows = []
    for method, g in ext.groupby("metodo"):
        ext_rows.append(prop_row(g["correcto"], conf, metodo=method, campo="(todos)"))
        ext_rows.append(prop_row(g["estado"] == "sin_verificar", conf, metodo=method, campo="(sin_verificar)"))
        for field, gf in g.groupby("campo"):
            ext_rows.append(prop_row(gf["correcto"], conf, metodo=method, campo=field))
    pd.DataFrame(ext_rows).to_csv(res / "extraction_ci.csv", index=False)

    # F1 macro del categórico y error absoluto de los numéricos
    rec_rows = []
    for method, g in ext.groupby("metodo"):
        lvl = g[g.campo == "nivel_ingles"]
        exp = [normalize_text(json.loads(v) or "") for v in lvl["esperado"]]
        pred = [normalize_text(json.loads(v) or "") or "(nulo)" for v in lvl["valor"]]
        rec_rows.append({"metodo": method, "metrica": "f1_macro_nivel_ingles", "valor": macro_f1(exp, pred),
                         "n": len(exp), "nota": f"clases: {', '.join(sorted(set(exp)))}"})
        for field in NUMERIC:
            gf = g[g.campo == field]
            pairs = [(json.loads(e), json.loads(v)) for e, v in zip(gf["esperado"], gf["valor"])]
            errors = [abs(v - e) for e, v in pairs if e is not None and v is not None]
            missing = sum(e is not None and v is None for e, v in pairs)
            rec_rows.append({"metodo": method, "metrica": f"error_abs_medio_{field}",
                             "valor": sum(errors) / len(errors) if errors else None, "n": len(errors),
                             "nota": f"{missing} sin valor extraído; errores: {errors}"})
    pd.DataFrame(rec_rows).to_csv(res / "record_metrics.csv", index=False)

    # ¿El WER predice el registro? Config por defecto (la que alimenta la extracción)
    default = bench_e[(bench_e.model == d["model"]) & (bench_e.requested_device == d["device"])
                      & (bench_e.compute_type == d["compute_type"])].copy()
    default["audio"] = default["audio"].str.replace(r"\.\w+$", "", regex=True)
    acc = ext.groupby(["audio", "metodo"])["correcto"].mean().unstack("metodo").add_prefix("acierto_")
    wvr = default.set_index("audio")[["wer", "cer"]].join(acc).sort_values("wer")
    # Mismo análisis sobre las llamadas degradadas: WER del nivel contra campos del pedido
    calls = pd.read_csv(res / "calls_validation.csv")
    calls["items_frac"] = calls["items_ok"].map(lambda s: int(s.split("/")[0]) / int(s.split("/")[1]))
    calls["acierto_pedido"] = calls[["items_frac", "promocion_ok", "pago_ok"]].astype(float).mean(axis=1)
    bl = bench_l.assign(llamada=bench_l["audio"].str.replace(r"\.\w+$", "", regex=True))[["llamada", "level", "wer", "cer"]]
    wvr_calls = bl.merge(calls[["llamada", "level", "acierto_pedido", "cuadra", "clasificacion"]], on=["llamada", "level"])
    wvr.reset_index().assign(set="entrevistas").to_csv(res / "wer_vs_record.csv", index=False)
    wvr_calls.sort_values("wer").to_csv(res / "wer_vs_record_llamadas.csv", index=False)

    # Tarea 2 por nivel: trampas detectadas y campos del pedido, con IC
    traps = pd.read_csv(res / "traps.csv")
    calls_rows = []
    for level, g in traps.groupby("level"):
        calls_rows.append(prop_row(g["detectada"], conf, level=level, medida="trampas detectadas"))
    for level, g in calls.groupby("level"):
        calls_rows.append(prop_row(g["promocion_ok"], conf, level=level, medida="promocion correcta"))
        calls_rows.append(prop_row(g["pago_ok"], conf, level=level, medida="metodo de pago correcto"))
        items = g["items_ok"].str.split("/", expand=True).astype(int)
        p, lo, hi = wilson_ci(int(items[0].sum()), int(items[1].sum()), conf)
        calls_rows.append({"level": level, "medida": "items correctos", "aciertos": int(items[0].sum()),
                           "n": int(items[1].sum()), "proporcion": p, "ic_bajo": lo, "ic_alto": hi})
    pd.DataFrame(calls_rows).to_csv(res / "calls_ci.csv", index=False)

    pd.set_option("display.width", 200)
    for name in ("asr_ci", "extraction_ci", "record_metrics", "wer_vs_record", "wer_vs_record_llamadas", "calls_ci"):
        print(f"\n== {name}\n" + pd.read_csv(res / f"{name}.csv").round(3).to_string(index=False))


if __name__ == "__main__":
    main()
