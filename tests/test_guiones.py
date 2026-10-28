"""Coherencia entre guiones, referencias y ground truth (antes de grabar)."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine import extract_rules
from engine.config import ROOT, load_config
from engine.metrics import normalize_text
from engine.validate import check_total
from engine.verify import verify_fields

CFG = load_config()
GT = ROOT / "data" / "ground_truth"
REFS = ROOT / "data" / "references"

# Casos que el extractor por reglas falla a propósito (ver docs/guiones/README.md)
EXPECTED_RULE_MISSES = {("entrevista_04", "disponibilidad")}


def load(name):
    return {k: v for k, v in json.loads((GT / name).read_text(encoding="utf-8")).items() if not k.startswith("_")}


def same(a, b):
    if isinstance(b, list):
        return {normalize_text(x) for x in a} == {normalize_text(x) for x in b}
    return (a is None and b is None) or (a is not None and b is not None and normalize_text(str(a)) == normalize_text(str(b)))


def test_rules_on_interview_scripts():
    for audio_id, expected in load("entrevistas.json").items():
        text = (REFS / f"{audio_id}.txt").read_text(encoding="utf-8")
        got = extract_rules.extract(text, CFG["extraction"]["technologies"])
        for field, value in expected.items():
            if (audio_id, field) in EXPECTED_RULE_MISSES:
                assert not same(got[field], value), f"{audio_id}.{field} ya no es un fallo esperado"
            else:
                assert same(got[field], value), f"{audio_id}.{field}: {got[field]!r} != {value!r}"


def test_ground_truth_values_appear_in_scripts():
    for audio_id, expected in load("entrevistas.json").items():
        text = (REFS / f"{audio_id}.txt").read_text(encoding="utf-8")
        present = {k: v for k, v in expected.items() if v is not None}
        for field, v in verify_fields(present, text).items():
            assert v["estado"] == "verificado", f"{audio_id}.{field} no aparece literal en el guion"


def test_call_totals_and_traps():
    calls = load("llamadas.json")
    traps = [t["tipo"] for c in calls.values() for t in c["trampas"]]
    assert traps.count("autocorreccion") >= 3
    assert traps.count("total_erroneo") >= 3
    assert traps.count("digitos") >= 1
    for call_id, c in calls.items():
        chk = check_total(c)
        assert chk["total_calculado"] == c["total_correcto"], call_id
        has_wrong_total = any(t["tipo"] == "total_erroneo" for t in c["trampas"])
        assert chk["cuadra"] != has_wrong_total, call_id
