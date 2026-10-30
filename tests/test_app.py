"""Smoke test de la app de Streamlit: carga sin errores y sin transcribir nada al iniciar."""
import ast
from pathlib import Path

from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parent.parent


def test_app_runs():
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=60).run()
    assert not at.exception
    # problema y método, corpus, resultados, pedidos, probador
    assert len(at.tabs) == 5


def test_app_only_calls_the_pipeline():
    """La app no importa la lógica de transcripción/extracción: solo engine.pipeline (y config)."""
    imported = {node.module for node in ast.walk(ast.parse((ROOT / "app.py").read_text(encoding="utf-8")))
                if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("engine")}
    assert imported <= {"engine.config", "engine.pipeline"}


def test_engine_has_no_ui_imports():
    for path in (ROOT / "engine").glob("*.py"):
        assert "streamlit" not in path.read_text(encoding="utf-8"), path.name


def test_pipeline_reports_errors_instead_of_raising():
    from engine.pipeline import process_audio

    result = process_audio(ROOT / "no_existe.wav", kind="entrevista", method="reglas", model="small")
    assert result["error"] and result["transcript"] is None and result["elapsed_s"] >= 0
