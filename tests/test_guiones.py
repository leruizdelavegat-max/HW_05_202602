"""Coherencia entre guiones, referencias y ground truth (antes de grabar)."""
import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine import extract_rules
from engine.config import ROOT, load_config
from engine.dates import to_absolute
from engine.metrics import normalize_text
from engine.validate import check_total
from engine.verify import appears_in

CFG = load_config()
GT = ROOT / "data" / "ground_truth"
REFS = ROOT / "data" / "references"

FIELDS = CFG["extraction"]["fields"]
# El extractor por reglas está pensado para frases limpias ("mi expectativa salarial es de…").
# Si acierta casi todo, el guion dice los datos demasiado limpio.
MIN_RULE_MISSES = 2


def load(name):
    return {k: v for k, v in json.loads((GT / name).read_text(encoding="utf-8")).items() if not k.startswith("_")}


def reference(audio_id):
    return (REFS / f"{audio_id}.txt").read_text(encoding="utf-8")


def same(a, b):
    if isinstance(b, list):
        return {normalize_text(x) for x in a} == {normalize_text(x) for x in b}
    return (a is None and b is None) or (a is not None and b is not None and normalize_text(str(a)) == normalize_text(str(b)))


def test_interview_evidence_is_literal():
    for audio_id, rec in load("entrevistas.json").items():
        text = reference(audio_id)
        for field, phrase in rec["evidencia"].items():
            assert (phrase is None) == (rec[field] is None), f"{audio_id}.{field}"
            if phrase is not None:
                assert appears_in(phrase, text), f"{audio_id}.{field}: «{phrase}» no aparece en el guion"
        for tech in rec["tecnologias"]:
            assert appears_in(tech, text), f"{audio_id}: {tech} no aparece en el guion"


def test_availability_is_stored_as_date():
    for audio_id, rec in load("entrevistas.json").items():
        ref = date.fromisoformat(rec["fecha_entrevista"])
        assert to_absolute(rec["evidencia"]["disponibilidad"], ref) == rec["disponibilidad"], audio_id


def test_field_order_varies_between_interviews():
    orders = []
    for audio_id, rec in load("entrevistas.json").items():
        text = normalize_text(reference(audio_id))
        found = {f: text.find(normalize_text(p)) for f, p in rec["evidencia"].items() if p}
        orders.append(tuple(sorted(found, key=found.get)))
    assert len(set(orders)) == len(orders), orders


def test_fields_are_not_said_cleanly():
    for audio_id, rec in load("entrevistas.json").items():
        ref = date.fromisoformat(rec["fecha_entrevista"])
        got = extract_rules.extract(reference(audio_id), CFG["extraction"]["technologies"], ref)
        got["disponibilidad"] = got["disponibilidad_fecha"]
        misses = [f for f in FIELDS if not same(got[f], rec[f])]
        assert len(misses) >= MIN_RULE_MISSES, f"{audio_id}: las reglas solo fallan en {misses}"


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


def test_call_records_are_complete_and_literal():
    for call_id, c in load("llamadas.json").items():
        text = reference(call_id)
        assert c["metodo_pago"] and appears_in(c["metodo_pago"], text), call_id
        assert appears_in(c["total_dicho"], text), call_id
        for item in c["items"]:
            assert "tamano" in item, f"{call_id}: {item['producto']} sin campo tamano"
            assert appears_in(item["precio_unitario"], text), f"{call_id}: precio de {item['producto']}"
        for trap in c["trampas"]:
            if trap["tipo"] == "digitos":
                for part in trap["esperado"].split(","):
                    assert appears_in(part.strip(), text), f"{call_id}: «{part.strip()}»"


def test_audio_length_fits_two_to_four_minutes():
    # Con el audio ya transcrito se usa su duración real; si no, se estima por palabras:
    # hablando rápido (~170 palabras por minuto), 2 min ≈ 340 palabras; despacio (~140), 4 min ≈ 560.
    cache = ROOT / "cache" / "transcripts"
    for ref in sorted(REFS.glob("*_0*.txt")):
        cached = sorted(cache.rglob(f"{ref.stem}__*.json"))
        if cached:
            seconds = json.loads(cached[0].read_text(encoding="utf-8"))["audio_duration_s"]
            assert 120 <= seconds <= 240, f"{ref.stem}: {seconds:.0f} s"
        else:
            words = len(ref.read_text(encoding="utf-8").split())
            assert 350 <= words <= 560, f"{ref.stem}: {words} palabras"
