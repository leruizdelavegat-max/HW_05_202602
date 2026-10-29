"""Disponibilidad: se dice en forma relativa ("en un mes", "el lunes") y se guarda como fecha absoluta.

La fecha de referencia es la de la entrevista (metadato de la grabación, no un campo a extraer).
"""
import calendar
import re
from datetime import date, timedelta

from engine.numbers import normalize_numbers, strip_accents

MONTHS = {m: i for i, m in enumerate(
    ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
     "agosto", "septiembre", "octubre", "noviembre", "diciembre"], start=1)}
WEEKDAYS = {d: i for i, d in enumerate(
    ["lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo"])}

_MONTH_RE = "|".join(MONTHS)
_DAY_RE = "|".join(WEEKDAYS)


def _add_months(ref: date, n: int) -> date:
    month = ref.month - 1 + n
    year, month = ref.year + month // 12, month % 12 + 1
    return date(year, month, min(ref.day, calendar.monthrange(year, month)[1]))


def to_absolute(phrase: str | None, ref: date) -> str | None:
    """Convierte una expresión de disponibilidad a fecha ISO, o None si no la entiende."""
    if not phrase:
        return None
    t = strip_accents(normalize_numbers(phrase).lower())
    t = re.sub(r"\b(un|una)\b", "1", t)

    if m := re.search(rf"(\d+|primero)\s+de\s+({_MONTH_RE})", t):
        day = 1 if m.group(1) == "primero" else int(m.group(1))
        d = date(ref.year, MONTHS[m.group(2)], day)
        return (d if d >= ref else d.replace(year=ref.year + 1)).isoformat()
    if m := re.search(rf"\b({_DAY_RE})\b", t):
        ahead = (WEEKDAYS[m.group(1)] - ref.weekday()) % 7 or 7
        return (ref + timedelta(days=ahead)).isoformat()
    if re.search(r"\bmanana\b", t):
        return (ref + timedelta(days=1)).isoformat()
    if re.search(r"inmediat|\bhoy\b|\bya mismo\b", t):
        return ref.isoformat()
    if m := re.search(r"(\d+)\s+(dias?|semanas?|mes(?:es)?)", t):
        n, unit = int(m.group(1)), m.group(2)
        if unit.startswith("mes"):
            return _add_months(ref, n).isoformat()
        return (ref + timedelta(days=n * (7 if unit.startswith("semana") else 1))).isoformat()
    return None
