"""Extracción con LLM (Claude) usando salida estructurada (JSON Schema).

El LLM solo propone valores; después engine.verify comprueba que aparezcan literalmente
en la transcripción. Lo que no aparezca queda como `sin_verificar`.
"""
import json

import anthropic

_NULLABLE_STR = {"type": ["string", "null"]}
_NULLABLE_INT = {"type": ["integer", "null"]}

INTERVIEW_SCHEMA = {
    "type": "object",
    "properties": {
        "anios_experiencia": _NULLABLE_INT,
        "ultimo_puesto": _NULLABLE_STR,
        "tecnologias": {"type": "array", "items": {"type": "string"}},
        "expectativa_salarial": _NULLABLE_INT,
        "disponibilidad": _NULLABLE_STR,
        "nivel_ingles": _NULLABLE_STR,
    },
    "required": [
        "anios_experiencia", "ultimo_puesto", "tecnologias",
        "expectativa_salarial", "disponibilidad", "nivel_ingles",
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
                    "cantidad": {"type": "number"},
                    "precio_unitario": {"type": ["number", "null"]},
                },
                "required": ["producto", "cantidad", "precio_unitario"],
                "additionalProperties": False,
            },
        },
        "promocion": {"type": ["number", "null"]},
        "total_declarado": {"type": ["number", "null"]},
        "direccion_o_contrato": _NULLABLE_STR,
        "autocorrecciones": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["items", "promocion", "total_declarado", "direccion_o_contrato", "autocorrecciones"],
    "additionalProperties": False,
}

INTERVIEW_PROMPT = """Extrae los datos del candidato de esta transcripción de entrevista.
Reglas:
- Copia los textos tal como aparecen en la transcripción; no parafrasees ni traduzcas.
- Convierte los números dichos en palabras a dígitos (ej. "seis mil quinientos" -> 6500).
- Si un dato no se menciona, devuelve null (o lista vacía para tecnologías). No inventes.

<transcripcion>
{transcript}
</transcripcion>"""

ORDER_PROMPT = """Extrae el pedido de esta transcripción de una llamada de venta ({domain}).
Reglas:
- Si el cliente se corrige ("dos... no, mejor tres"), usa el valor FINAL y anota la corrección en `autocorrecciones`.
- `total_declarado` es el total que dice en voz alta el vendedor o el cliente, aunque esté mal calculado. No lo corrijas.
- `promocion` es el descuento en moneda (no porcentaje); null si no hay.
- Copia direcciones y números de contrato tal como aparecen.
- Si un dato no se menciona, devuelve null. No inventes.

<transcripcion>
{transcript}
</transcripcion>"""


def _call(prompt: str, schema: dict, cfg: dict) -> dict:
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


def extract_interview(transcript: str, cfg: dict) -> dict:
    return _call(INTERVIEW_PROMPT.format(transcript=transcript), INTERVIEW_SCHEMA, cfg)


def extract_order(transcript: str, domain: str, cfg: dict) -> dict:
    return _call(ORDER_PROMPT.format(transcript=transcript, domain=domain), ORDER_SCHEMA, cfg)
