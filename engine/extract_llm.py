"""Extracción con LLM usando salida estructurada (JSON Schema).

Dos proveedores, según `extraction.llm.provider` en config.yaml:
- `ollama`: modelo local y gratuito (sin API key); Ollama restringe la salida al esquema.
- `anthropic`: Claude por API (requiere ANTHROPIC_API_KEY en .env).

El LLM solo propone valores; después engine.verify comprueba que aparezcan literalmente
en la transcripción. Lo que no aparezca queda como `sin_verificar`.
"""
import json
import urllib.request
from datetime import date

from engine.dates import to_absolute

_NULLABLE_STR = {"type": ["string", "null"]}
_NULLABLE_INT = {"type": ["integer", "null"]}

INTERVIEW_SCHEMA = {
    "type": "object",
    "properties": {
        "anios_experiencia": _NULLABLE_INT,
        "ultimo_puesto": _NULLABLE_STR,
        "tecnologias": {"type": "array", "items": {"type": "string"}},
        "pretension_salarial": _NULLABLE_INT,
        "disponibilidad": _NULLABLE_STR,
        "disponibilidad_fecha": _NULLABLE_STR,
        "nivel_ingles": _NULLABLE_STR,
    },
    "required": [
        "anios_experiencia", "ultimo_puesto", "tecnologias",
        "pretension_salarial", "disponibilidad", "disponibilidad_fecha", "nivel_ingles",
    ],
    "additionalProperties": False,
}

ORDER_SCHEMA = {
    "type": "object",
    "properties": {
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "producto": {"type": "string"},
                    "tamano": _NULLABLE_STR,
                    "cantidad": {"type": "number"},
                    "precio_unitario": {"type": ["number", "null"]},
                },
                "required": ["producto", "tamano", "cantidad", "precio_unitario"],
                "additionalProperties": False,
            },
        },
        "promocion": {"type": ["number", "null"]},
        "direccion_o_contrato": _NULLABLE_STR,
        "metodo_pago": _NULLABLE_STR,
        "total_dicho": {"type": ["number", "null"]},
        "autocorrecciones": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["items", "promocion", "direccion_o_contrato", "metodo_pago", "total_dicho", "autocorrecciones"],
    "additionalProperties": False,
}


def _call(prompt: str, schema: dict, cfg: dict) -> dict:
    if cfg.get("provider", "anthropic") == "ollama":
        return _call_ollama(prompt, schema, cfg)
    return _call_anthropic(prompt, schema, cfg)


def _call_ollama(prompt: str, schema: dict, cfg: dict) -> dict:
    body = {
        "model": cfg["model"],
        "messages": [{"role": "user", "content": prompt}],
        "format": schema,  # Ollama genera solo JSON que cumple el esquema
        "stream": False,
        "options": {"temperature": 0, "num_ctx": cfg["num_ctx"]},
    }
    request = urllib.request.Request(
        f"{cfg['base_url']}/api/chat",
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=cfg["timeout_s"]) as response:
        return json.loads(json.loads(response.read())["message"]["content"])


def _call_anthropic(prompt: str, schema: dict, cfg: dict) -> dict:
    import anthropic

    client = anthropic.Anthropic()
    response = client.beta.messages.create(
        model=cfg["model"],
        max_tokens=cfg.get("max_tokens", 4000),
        output_config={"effort": cfg.get("effort", "low"),
                       "format": {"type": "json_schema", "schema": schema}},
        # Si el modelo principal rechaza la petición, la API reintenta con un modelo alternativo
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        messages=[{"role": "user", "content": prompt}],
    )
    if response.stop_reason == "refusal":
        raise RuntimeError(f"El modelo rechazó la petición: {response.stop_details}")
    text = next(b.text for b in response.content if b.type == "text")
    return json.loads(text)


_WEEKDAYS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]


def extract_interview(transcript: str, cfg: dict, ref_date: date) -> dict:
    prompt = cfg["prompts"]["entrevista"].format(transcript=transcript, fecha=ref_date.isoformat(),
                                                 dia_semana=_WEEKDAYS[ref_date.weekday()])
    result = _call(prompt, INTERVIEW_SCHEMA, cfg)
    # Los modelos pequeños fallan la aritmética de calendario ("el lunes" desde un jueves):
    # el LLM aporta la frase y la fecha la calcula el mismo código que usan las reglas.
    # Si ese código no entiende la frase, se queda la fecha que propuso el LLM.
    result["disponibilidad_fecha"] = (to_absolute(result.get("disponibilidad"), ref_date)
                                      or result.get("disponibilidad_fecha"))
    return result


def extract_order(transcript: str, domain: str, cfg: dict) -> dict:
    return _call(cfg["prompts"]["pedido"].format(transcript=transcript, domain=domain), ORDER_SCHEMA, cfg)
