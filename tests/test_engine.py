"""Pruebas del motor que no necesitan GPU, audio ni API key.

  python -m pytest tests      (o simplemente: python tests/test_engine.py)
"""
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np

from engine import extract_rules
from engine.dates import to_absolute
from engine.degrade import add_noise, measured_snr_db, phone, whatsapp
from engine.metrics import wer_cer
from engine.numbers import normalize_numbers
from engine.validate import check_total, classify_error
from engine.verify import verify_fields

INTERVIEW = (
    "Hola, tengo cinco años de experiencia. Mi último puesto fue analista de datos en un banco. "
    "Manejo Python, SQL y Power BI. Mi expectativa salarial es de seis mil quinientos soles. "
    "Tengo disponibilidad en dos semanas y mi nivel de inglés es intermedio."
)


def test_numbers():
    assert normalize_numbers("espero seis mil quinientos soles") == "espero 6500 soles"
    assert normalize_numbers("tengo treinta y cinco años") == "tengo 35 años"
    assert normalize_numbers("un puesto de analista") == "un puesto de analista"
    assert normalize_numbers("dos millones quinientos mil") == "2500000"
    assert normalize_numbers("mil doscientos treinta y cuatro") == "1234"
    assert normalize_numbers("veintiún días") == "21 días"


def test_rules_extraction():
    r = extract_rules.extract(INTERVIEW, ["python", "sql", "power bi", "r", "excel"])
    assert r == {
        "anios_experiencia": 5,
        "ultimo_puesto": "analista de datos",
        "expectativa_salarial": 6500,
        "disponibilidad": "en 2 semanas",
        "nivel_ingles": "intermedio",
        "tecnologias": ["python", "sql", "power bi"],
    }


def test_relative_dates():
    jueves = date(2026, 10, 29)
    assert to_absolute("inmediata", jueves) == "2026-10-29"
    assert to_absolute("desde mañana", jueves) == "2026-10-30"
    assert to_absolute("el lunes mismo", jueves) == "2026-11-02"
    assert to_absolute("en dos semanas", jueves) == "2026-11-12"
    assert to_absolute("necesitaría un mes", jueves) == "2026-11-29"
    assert to_absolute("a partir del primero de diciembre", jueves) == "2026-12-01"
    assert to_absolute("15 de enero", jueves) == "2027-01-15"
    assert to_absolute("cuando pueda", jueves) is None
    r = extract_rules.extract(INTERVIEW, ["python"], jueves)
    assert r["disponibilidad_fecha"] == "2026-11-12"


def test_literal_verification():
    v = verify_fields({"ultimo_puesto": "analista de datos", "expectativa_salarial": 6500,
                       "tecnologias": ["python", "excel"], "nivel_ingles": "gerente general"}, INTERVIEW)
    assert v["ultimo_puesto"]["estado"] == "verificado"
    assert v["expectativa_salarial"]["estado"] == "verificado"   # 6500 vs. "seis mil quinientos"
    assert v["tecnologias"]["estado"] == "sin_verificar"         # excel no se menciona
    assert v["nivel_ingles"]["estado"] == "sin_verificar"


def test_metrics_normalize_numbers():
    assert wer_cer("Espero seis mil quinientos soles.", "espero 6.500 soles")["wer"] == 0


def test_arithmetic_and_classification():
    order = {"items": [{"producto": "pizza", "cantidad": 3, "precio_unitario": 45},
                       {"producto": "gaseosa", "cantidad": 2, "precio_unitario": 8}],
             "promocion": 10, "total_dicho": 155}
    c = check_total(order)
    assert c["total_calculado"] == 141 and not c["cuadra"]
    assert classify_error({"L0": 155, "L1": 155, "L2": 155}, 141) == "error_hablante"
    assert classify_error({"L0": 155, "L1": 165}, 141) == "error_asr"
    assert classify_error({"L0": 141, "L1": 141}, 141) == "sin_error"


def test_degradation():
    x = (np.sin(np.linspace(0, 2000, 32000)) * 0.3).astype("float32")
    assert abs(measured_snr_db(x, add_noise(x, 10)) - 10) < 0.5
    assert len(phone(x, 16000)) == len(x)
    compressed = whatsapp(x, 16000)
    assert len(compressed) == len(x) and measured_snr_db(x, compressed) > 5


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
