"""Extractor por reglas (regex) para los seis campos de la entrevista.

Trabaja sobre el texto con números normalizados, así "seis mil quinientos" ya llega como 6500.
Ajusta los patrones a cómo hablas tú en tus grabaciones.
"""
import re
from datetime import date

from engine.dates import to_absolute
from engine.numbers import normalize_numbers, strip_accents

_PATTERNS = {
    "anios_experiencia": [
        r"(\d+)\s+anos?\s+de\s+experiencia",
        r"experiencia\s+de\s+(\d+)\s+anos?",
        r"llevo\s+(\d+)\s+anos?",
    ],
    "ultimo_puesto": [
        r"(?:mi\s+ultimo\s+(?:puesto|cargo|trabajo)\s+(?:fue|era)\s+(?:de\s+|como\s+)?)([a-z ]{3,60}?)(?=[.,;]| en | para |$)",
        r"(?:trabaje|me desempene|estuve)\s+como\s+([a-z ]{3,60}?)(?=[.,;]| en | para |$)",
    ],
    "pretension_salarial": [
        r"(?:expectativa|pretension|aspiracion)\s+salarial[^\d]{0,40}(\d+)",
        r"(?:espero|aspiro a|quisiera)\s+(?:ganar|recibir)?[^\d]{0,30}(\d+)",
    ],
    "disponibilidad": [
        r"(inmediata)",
        r"(desde\s+manana|manana\s+mismo)",
        r"(en\s+\d+\s+(?:semanas?|mes(?:es)?|dias?))",
        r"(\d+\s+dias\s+de\s+preaviso)",
        r"(a\s+partir\s+del?\s+[a-z0-9 ]{3,30}?)(?=[.,;]|$)",
    ],
    "nivel_ingles": [
        r"ingles[^.]{0,40}?\b(basico|intermedio|avanzado|nativo|fluido|[abc][12])\b",
        r"\b(basico|intermedio|avanzado|fluido|[abc][12])\b[^.]{0,20}ingles",
    ],
}


def _prepare(transcript: str) -> str:
    return strip_accents(normalize_numbers(transcript).lower())


def extract(transcript: str, technologies: list[str], ref_date: date | None = None) -> dict:
    """Con `ref_date` (fecha de la entrevista) agrega `disponibilidad_fecha` en formato ISO."""
    text = _prepare(transcript)
    result = {}
    for field, patterns in _PATTERNS.items():
        value = None
        for pattern in patterns:
            m = re.search(pattern, text)
            if m:
                value = m.group(1).strip()
                break
        if value is not None and field in ("anios_experiencia", "pretension_salarial"):
            value = int(value)
        result[field] = value

    result["tecnologias"] = [
        tech for tech in technologies
        if re.search(rf"(?<!\w){re.escape(strip_accents(tech.lower()))}(?!\w)", text)
    ]
    if ref_date is not None:
        result["disponibilidad_fecha"] = to_absolute(result["disponibilidad"], ref_date)
    return result
