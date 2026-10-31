"""Comprueba que todo el código importa con las dependencias instaladas (sin GPU ni API key)."""
import importlib
import inspect
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def test_modules_import():
    for name in ["engine.asr", "engine.extract_llm", "engine.degrade", "engine.validate",
                 "scripts.transcribe", "scripts.degrade", "scripts.extract_interviews", "scripts.validate_calls"]:
        importlib.import_module(name)


def test_anthropic_sdk_supports_params():
    import anthropic

    params = inspect.signature(anthropic.Anthropic(api_key="x").beta.messages.create).parameters
    for p in ("output_config", "betas", "fallbacks"):
        assert p in params, f"el SDK no acepta {p}"
