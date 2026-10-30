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
        "disponibilidad_fecha": _NULLABLE_STR,
        "nivel_ingles": _NULLABLE_STR,
    },
    "required": [
        "anios_experiencia", "ultimo_puesto", "tecnologias",
        "expectativa_salarial", "disponibilidad", "disponibilidad_fecha", "nivel_ingles",
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

INTERVIEW_PROMPT = """Extrae los datos del candidato de esta transcripción de entrevista.
La entrevista se realizó el {fecha} ({dia_semana}).
Reglas:
- Copia los textos tal como aparecen en la transcripción; no parafrasees ni traduzcas.
- Convierte los números dichos en palabras a dígitos (ej. "seis mil quinientos" -> 6500).
- Si el candidato se corrige, usa el valor final. Si da un rango y luego una cifra, usa la cifra.
- `tecnologias`: solo las que usó en su trabajo, no las que quiere aprender o dejó de usar.
- `nivel_ingles`: uno de básico, intermedio, avanzado o fluido, según lo que dice que habla realmente.
- `disponibilidad`: la frase tal como la dice; `disponibilidad_fecha`: esa fecha en formato AAAA-MM-DD,
  calculada desde la fecha de la entrevista ("inmediata" = el mismo día).
- Si un dato no se menciona, devuelve null (o lista vacía para tecnologías). No inventes.

<transcripcion>
{transcript}
</transcripcion>"""

ORDER_PROMPT = """Extrae el pedido de esta transcripción de una llamada de venta ({domain}).
Reglas:
- Si el cliente se corrige ("dos... no, mejor tres"), usa el valor FINAL y anota la corrección en `autocorrecciones`.
- `tamano` va aparte del producto ("pizza de jamón" + "familiar"); null si el producto no tiene tamaño.
- `precio_unitario` es el del tamaño que se pidió, no el de otros tamaños que se mencionan.
- `total_dicho` es el total que dice en voz alta el vendedor o el cliente, aunque esté mal calculado. No lo corrijas.
- `promocion` es el descuento en moneda (no porcentaje) que se aplica a este pedido; null si no hay o no aplica.
- `metodo_pago`: efectivo, tarjeta, Yape, etc.; null si no se dice.
- Copia direcciones y números de contrato tal como aparecen.
- Si un dato no se menciona, devuelve null. No inventes.

<transcripcion>
{transcript}
</transcripcion>"""


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
        "options": {"temperature": 0, "num_ctx": cfg.get("num_ctx", 4096)},
    }
    request = urllib.request.Request(
        f"{cfg.get('base_url', 'http://localhost:11434')}/api/chat",
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=cfg.get("timeout_s", 900)) as response:
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
    prompt = INTERVIEW_PROMPT.format(transcript=transcript, fecha=ref_date.isoformat(),
                                     dia_semana=_WEEKDAYS[ref_date.weekday()])
    return _call(prompt, INTERVIEW_SCHEMA, cfg)


def extract_order(transcript: str, domain: str, cfg: dict) -> dict:
    return _call(ORDER_PROMPT.format(transcript=transcript, domain=domain), ORDER_SCHEMA, cfg)
