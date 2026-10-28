"""Regla de evidencia literal: todo valor extraído debe aparecer en la transcripción.

Si no aparece (tras normalizar acentos, mayúsculas y números hablados), se marca `sin_verificar`.
"""
from engine.metrics import normalize_text

SIN_VERIFICAR = "sin_verificar"


def appears_in(value, transcript: str) -> bool:
    if value is None or value == "":
        return False
    haystack = f" {normalize_text(transcript)} "
    needle = normalize_text(str(value))
    return bool(needle) and f" {needle} " in haystack


def verify_fields(fields: dict, transcript: str) -> dict:
    """{campo: valor} -> {campo: {"valor": ..., "estado": "verificado" | "sin_verificar"}}.

    Para listas (tecnologías) se verifica cada elemento por separado.
    """
    out = {}
    for name, value in fields.items():
        if isinstance(value, list):
            items = [
                {"valor": v, "estado": "verificado" if appears_in(v, transcript) else SIN_VERIFICAR}
                for v in value
            ]
            ok = bool(items) and all(i["estado"] == "verificado" for i in items)
            out[name] = {"valor": value, "estado": "verificado" if ok else SIN_VERIFICAR, "items": items}
        else:
            ok = appears_in(value, transcript)
            out[name] = {"valor": value, "estado": "verificado" if ok else SIN_VERIFICAR}
    return out
