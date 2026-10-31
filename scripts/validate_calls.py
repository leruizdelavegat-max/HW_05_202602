"""Tarea 2: extrae el pedido en cada nivel L0-L3, valida la aritmética y reporta trampas detectadas.

  python scripts/validate_calls.py
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd

from engine.asr import cache_path, load_cached
from engine.config import load_config, resolve
from engine.extract_llm import extract_order
from engine.metrics import normalize_text
from engine.validate import check_total, classify_error


def digits(text) -> str:
    return re.sub(r"\D", "", str(text or ""))


def trap_caught(trap: dict, order: dict, check: dict, classification: str) -> bool:
    kind = trap["tipo"]
    if kind == "autocorreccion":
        target = normalize_text(trap["producto"])
        return any(target in normalize_text(i["producto"]) and i["cantidad"] == trap["cantidad_final"]
                   for i in order["items"])
    if kind == "total_erroneo":
        return not check["cuadra"] and classification == "error_hablante"
    if kind == "digitos":
        return digits(trap["esperado"]) != "" and digits(trap["esperado"]) in digits(order.get("direccion_o_contrato"))
    raise ValueError(f"tipo de trampa desconocido: {kind}")


def item_matches(expected: dict, item: dict) -> bool:
    want, got = normalize_text(expected["tamano"] or ""), normalize_text(item.get("tamano") or "")
    size_ok = not want or (bool(got) and (want in got or got in want))  # "familiares" ~ "familiar"
    return (normalize_text(expected["producto"]) in normalize_text(item["producto"]) and size_ok
            and item["cantidad"] == expected["cantidad"] and item["precio_unitario"] == expected["precio_unitario"])


def record_fields(expected: dict, order: dict) -> dict:
    """Aciertos del registro completo, no solo de las trampas."""
    found = sum(any(item_matches(e, i) for i in order["items"]) for e in expected["items"])
    return {
        "items_ok": f"{found}/{len(expected['items'])}",
        "promocion_ok": (order.get("promocion") or None) == expected["promocion"],
        "pago_ok": normalize_text(expected["metodo_pago"]) in normalize_text(order.get("metodo_pago") or ""),
    }


def main():
    cfg = load_config()
    d = cfg["asr"]["default"]
    levels = list(cfg["degradation"]["levels"])
    tol = cfg["calls"]["total_tolerance"]
    gt = json.loads((resolve(cfg["paths"]["ground_truth"]) / "llamadas.json").read_text(encoding="utf-8"))
    cache_root = resolve(cfg["paths"]["cache"]) / "llamadas"
    out_dir = resolve(cfg["paths"]["results"])
    out_dir.mkdir(parents=True, exist_ok=True)
    orders_cache = out_dir / "orders.json"
    orders = json.loads(orders_cache.read_text(encoding="utf-8")) if orders_cache.exists() else {}

    level_rows, trap_rows = [], []
    for call_id, expected in gt.items():
        if call_id.startswith("_"):
            continue
        per_level = {}
        for lvl in levels:
            cached = load_cached(cache_path(cache_root / lvl, call_id, d["model"], d["device"], d["compute_type"]))
            if cached is None:
                print(f"[aviso] falta transcripción {call_id} {lvl}")
                continue
            key = f"{call_id}/{lvl}"
            if key not in orders:  # cachea la respuesta del LLM para no pagar dos veces
                orders[key] = extract_order(cached["text"], cfg["calls"]["domain"], cfg["extraction"]["llm"])
                orders_cache.write_text(json.dumps(orders, ensure_ascii=False, indent=2), encoding="utf-8")
            per_level[lvl] = (orders[key], check_total(orders[key], tol))

        if "L0" not in per_level:
            continue
        classification = classify_error(
            {lvl: chk["total_dicho"] for lvl, (_, chk) in per_level.items()},
            per_level["L0"][1]["total_calculado"], tol,
        )
        for lvl, (order, chk) in per_level.items():
            level_rows.append({"llamada": call_id, "level": lvl, **{k: v for k, v in chk.items() if k != "items_sin_precio"},
                               **record_fields(expected, order), "clasificacion": classification})
            for trap in expected.get("trampas", []):
                trap_rows.append({"llamada": call_id, "level": lvl, "trampa": trap["id"], "tipo": trap["tipo"],
                                  "detectada": trap_caught(trap, order, chk, classification)})

    pd.DataFrame(level_rows).to_csv(out_dir / "calls_validation.csv", index=False)
    traps = pd.DataFrame(trap_rows)
    traps.to_csv(out_dir / "traps.csv", index=False)
    if not traps.empty:
        print(traps.pivot_table(index=["llamada", "trampa", "tipo"], columns="level", values="detectada"))


if __name__ == "__main__":
    main()
