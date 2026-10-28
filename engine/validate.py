"""Validación aritmética del pedido y clasificación de errores (ASR vs. hablante)."""


def check_total(order: dict, tolerance: float = 0.01) -> dict:
    """Σ(cantidad × precio) − promoción == total declarado."""
    missing = [i["producto"] for i in order["items"] if i.get("precio_unitario") is None]
    subtotal = sum(i["cantidad"] * (i["precio_unitario"] or 0) for i in order["items"])
    computed = subtotal - (order.get("promocion") or 0)
    declared = order.get("total_declarado")
    ok = declared is not None and not missing and abs(computed - declared) <= tolerance
    return {
        "subtotal": subtotal,
        "total_calculado": computed,
        "total_declarado": declared,
        "diferencia": None if declared is None else declared - computed,
        "cuadra": ok,
        "items_sin_precio": missing,
    }


def classify_error(declared_by_level: dict[str, float | None], computed_l0: float,
                   tolerance: float = 0.01) -> str:
    """Propuesta de regla para separar error del hablante de error del ASR.

    Idea: un error del hablante (dijo mal el total) es estable, se transcribe igual en todos
    los niveles. Un error del ASR depende de la calidad del audio, cambia entre niveles.
      - el total declarado es el mismo en todos los niveles y no cuadra -> error_hablante
      - el total declarado cambia entre niveles                          -> error_asr
      - todos los niveles cuadran                                       -> sin_error
    Esta regla es un punto de partida: compárala con tu ground truth y ajústala.
    """
    values = [v for v in declared_by_level.values() if v is not None]
    if not values:
        return "total_no_detectado"
    stable = max(values) - min(values) <= tolerance
    if stable:
        return "sin_error" if abs(values[0] - computed_l0) <= tolerance else "error_hablante"
    return "error_asr"
