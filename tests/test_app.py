"""Smoke test de la app de Streamlit: debe cargar sin errores aunque results/ esté vacío."""
from pathlib import Path

from streamlit.testing.v1 import AppTest


def test_app_runs():
    at = AppTest.from_file(str(Path(__file__).resolve().parent.parent / "app.py"), default_timeout=60).run()
    assert not at.exception
    assert len(at.tabs) == 4
