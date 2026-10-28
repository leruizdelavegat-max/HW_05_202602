"""De la voz al registro: app de Streamlit.

  streamlit run app.py

Lee las transcripciones cacheadas y los resultados en results/. No necesita GPU ni audio.
"""
import json
import tempfile
from pathlib import Path

import pandas as pd
import streamlit as st

from engine import extract_rules
from engine.config import load_config, resolve
from engine.verify import verify_fields

cfg = load_config()
CACHE = resolve(cfg["paths"]["cache"])
RESULTS = resolve(cfg["paths"]["results"])

st.set_page_config(page_title="De la voz al registro", layout="wide")
st.title("De la voz al registro")


def read_csv(name: str) -> pd.DataFrame | None:
    path = RESULTS / name
    return pd.read_csv(path) if path.exists() else None


def show_fields(verified: dict):
    table = pd.DataFrame(
        [{"campo": k, "valor": json.dumps(v["valor"], ensure_ascii=False), "estado": v["estado"]}
         for k, v in verified.items()]
    )
    st.dataframe(table, hide_index=True, use_container_width=True)


tab_asr, tab_bench, tab_extract, tab_calls = st.tabs(
    ["1 · Transcripción", "2 · Comparación ASR", "3 · Extracción", "4 · Llamadas de venta"]
)

with tab_asr:
    st.subheader("Transcripciones cacheadas")
    files = sorted(CACHE.rglob("*.json"))
    if not files:
        st.info("Aún no hay transcripciones. Corre `python scripts/transcribe.py --set entrevistas`.")
    else:
        choice = st.selectbox("Transcripción", files, format_func=lambda p: str(p.relative_to(CACHE)))
        data = json.loads(choice.read_text(encoding="utf-8"))
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Dispositivo (runtime)", data["runtime_device"])
        c2.metric("Precisión", data["compute_type"])
        c3.metric("Tiempo (s)", f"{data['transcribe_s']:.1f}")
        c4.metric("Pico VRAM (MiB)", "—" if data["vram_peak_mib"] is None else f"{data['vram_peak_mib']:.0f}")
        st.text_area("Texto", data["text"], height=200)
        st.dataframe(pd.DataFrame(data["segments"]), hide_index=True, use_container_width=True)

    with st.expander("Transcribir un audio nuevo (en vivo)"):
        upload = st.file_uploader("Audio", type=["wav", "m4a", "mp3", "ogg"])
        model = st.selectbox("Modelo", cfg["asr"]["models"])
        if upload and st.button("Transcribir"):
            from engine.asr import transcribe

            with tempfile.NamedTemporaryFile(suffix=Path(upload.name).suffix, delete=False) as tmp:
                tmp.write(upload.read())
            with st.spinner("Transcribiendo..."):
                d = cfg["asr"]["default"]
                result = transcribe(Path(tmp.name), model, d["device"], d["compute_type"], cfg["asr"]["language"])
            st.session_state["live_transcript"] = result["text"]
            st.write(f"Dispositivo: **{result['runtime_device']}** · {result['transcribe_s']:.1f} s")
            st.text_area("Resultado", result["text"], height=150)

with tab_bench:
    st.subheader("Modelos × dispositivo × precisión")
    df = read_csv("benchmark_entrevistas.csv")
    if df is None:
        st.info("Corre `python scripts/transcribe.py --set entrevistas` para generar el benchmark.")
    else:
        group = ["model", "runtime_device", "compute_type"]
        metrics = [c for c in ["wer", "cer", "transcribe_s", "rtf", "vram_peak_mib"] if c in df]
        summary = df.groupby(group)[metrics].mean().reset_index()
        summary["config"] = summary[group].astype(str).agg(" / ".join, axis=1)
        st.dataframe(summary.drop(columns="config").round(3), hide_index=True, use_container_width=True)
        metric = st.radio("Métrica", metrics, horizontal=True)
        st.bar_chart(summary, x="config", y=metric)
        with st.expander("Detalle por audio"):
            st.dataframe(df, hide_index=True, use_container_width=True)

with tab_extract:
    st.subheader("Reglas vs. LLM, con verificación literal")
    df = read_csv("extraction.csv")
    if df is not None:
        acc = df.groupby(["campo", "metodo"])["correcto"].mean().unstack().round(2)
        st.write("Exactitud por campo")
        st.dataframe(acc, use_container_width=True)
        details = json.loads((RESULTS / "extraction.json").read_text(encoding="utf-8"))
        audio = st.selectbox("Entrevista", list(details))
        cols = st.columns(len(details[audio]))
        for col, (method, verified) in zip(cols, details[audio].items()):
            with col:
                st.markdown(f"**{method}**")
                show_fields(verified)
    else:
        st.info("Corre `python scripts/extract_interviews.py` para generar los resultados.")

    st.divider()
    st.write("Probar el extractor por reglas sobre un texto")
    text = st.text_area("Transcripción", st.session_state.get("live_transcript", ""), height=120)
    if text:
        show_fields(verify_fields(extract_rules.extract(text, cfg["extraction"]["technologies"]), text))

with tab_calls:
    st.subheader(f"Captura de pedidos · {cfg['calls']['domain']}")
    val, traps, deg = read_csv("calls_validation.csv"), read_csv("traps.csv"), read_csv("degradation.csv")
    bench = read_csv("benchmark_llamadas.csv")
    if val is None:
        st.info("Corre `scripts/degrade.py`, `scripts/transcribe.py --set llamadas` y `scripts/validate_calls.py`.")
    else:
        if bench is not None and "wer" in bench:
            st.write("Capa 1 · Calidad de transcripción por nivel")
            st.line_chart(bench.groupby("level")[["wer", "cer"]].mean())
        if traps is not None and not traps.empty:
            st.write("Capa 2 · Trampas detectadas por nivel")
            st.bar_chart(traps.groupby("level")["detectada"].mean())
            st.dataframe(traps.pivot_table(index=["llamada", "trampa", "tipo"], columns="level",
                                           values="detectada"), use_container_width=True)
        st.write("Validación aritmética")
        st.dataframe(val, hide_index=True, use_container_width=True)
        if deg is not None:
            with st.expander("SNR medido por nivel"):
                st.dataframe(deg, hide_index=True, use_container_width=True)
