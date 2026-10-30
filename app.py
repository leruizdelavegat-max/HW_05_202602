"""De la voz al registro: app de Streamlit.

  streamlit run app.py

Carga resultados precalculados (cache/transcripts/ y results/); no transcribe el corpus al iniciar.
Solo el probador transcribe, y lo hace llamando a engine.pipeline.process_audio.
"""
import json
import tempfile
from datetime import date
from pathlib import Path

import pandas as pd
import streamlit as st

from engine.config import load_config, resolve

cfg = load_config()
CACHE = resolve(cfg["paths"]["cache"])
RESULTS = resolve(cfg["paths"]["results"])
GROUND_TRUTH = resolve(cfg["paths"]["ground_truth"])
AUDIO = resolve(cfg["paths"]["audio_raw"])
AUDIO_DEGRADED = resolve(cfg["paths"]["audio_degraded"])
DEFAULT = cfg["asr"]["default"]
AUDIO_EXT = [".wav", ".mp3", ".m4a", ".ogg", ".flac"]
LEVEL_NAMES = {"L0": "L0 · original", "L1": "L1 · WhatsApp (Opus 16 kbps)",
               "L2": "L2 · teléfono (8 kHz)", "L3": "L3 · ruido a 10 dB"}

st.set_page_config(page_title="De la voz al registro", layout="wide")
st.title("De la voz al registro")


def read_csv(name: str) -> pd.DataFrame | None:
    path = RESULTS / name
    return pd.read_csv(path) if path.exists() else None


def read_json(path: Path) -> dict | None:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def find_audio(folder: Path, stem: str) -> Path | None:
    return next((folder / f"{stem}{ext}" for ext in AUDIO_EXT if (folder / f"{stem}{ext}").exists()), None)


def cached_transcript(dataset: str, stem: str, level: str | None = None) -> dict | None:
    folder = CACHE / dataset / level if level else CACHE / dataset
    return read_json(folder / f"{stem}__{DEFAULT['model']}__{DEFAULT['device']}__{DEFAULT['compute_type']}.json")


def fields_table(verified: dict) -> pd.DataFrame:
    return pd.DataFrame([
        {"campo": k, "valor": json.dumps(v["valor"], ensure_ascii=False),
         "fecha": v.get("fecha") or "", "estado": v["estado"]}
        for k, v in verified.items()
    ])


def pct(x: float) -> str:
    return f"{x:.1%}"


tab_method, tab_corpus, tab_results, tab_orders, tab_tester = st.tabs(
    ["1 · Problema y método", "2 · Corpus", "3 · Resultados", "4 · Pedidos (llamadas)", "5 · Probador"]
)

# ---------------------------------------------------------------- 1. Problema y método
with tab_method:
    st.subheader("El problema")
    st.markdown(
        """
Las entrevistas de trabajo y las llamadas de venta se graban, pero los datos que importan
(salario pedido, disponibilidad, productos, precios, dirección) quedan atrapados en el audio. Alguien
tiene que escucharlo y copiarlos a mano. Este proyecto convierte el audio en un **registro
estructurado y verificable**: cada valor tiene que aparecer literalmente en la transcripción, y lo que
no aparece se marca `sin_verificar` en vez de inventarse.
"""
    )
    st.subheader("El método")
    st.markdown(
        f"""
1. **Transcripción** con Whisper (faster-whisper). Se compararon `small` y `medium`, en CPU y GPU,
   con dos precisiones cada uno. Por defecto: `{DEFAULT['model']}` / `{DEFAULT['device']}` /
   `{DEFAULT['compute_type']}`.
2. **Extracción** por dos caminos sobre la misma transcripción: **reglas** (expresiones regulares) y
   un **LLM** local y gratuito (`{cfg['extraction']['llm']['model']}` con Ollama), con salida
   restringida a un JSON Schema.
3. **Normalización**: los números dichos en palabras pasan a dígitos («siete mil» → 7000) y la
   disponibilidad relativa («el lunes») pasa a fecha absoluta desde la fecha de la entrevista.
4. **Verificación literal**: cada valor se busca en la transcripción; si no está, `sin_verificar`.
5. **Llamadas de venta** ({cfg['calls']['domain']}): el audio se degrada en una escalera L0–L3
   (WhatsApp, teléfono, ruido) y en cada nivel se extrae el pedido y se valida la aritmética:
   Σ(cantidad × precio) − promoción = total dicho.
6. **Error del ASR vs. error del hablante**: si el total dicho es el mismo en todos los niveles y no
   cuadra, lo dijo mal el hablante; si cambia entre niveles, es un error del ASR.
"""
    )
    st.caption("Todos los audios son inventados y grabados con consentimiento. Detalle en el README.")

# ---------------------------------------------------------------- 2. Corpus
with tab_corpus:
    dataset = st.radio("Conjunto", ["entrevistas", "llamadas"], horizontal=True)
    gt = read_json(GROUND_TRUTH / f"{dataset}.json") or {}
    stems = [k for k in gt if not k.startswith("_")]
    c_sel, c_lvl = st.columns([2, 1])
    stem = c_sel.selectbox("Audio", stems)
    level = c_lvl.selectbox("Nivel", list(LEVEL_NAMES), format_func=LEVEL_NAMES.get) if dataset == "llamadas" else None

    left, right = st.columns([1, 2])
    with left:
        audio = (find_audio(AUDIO / dataset, stem) if level in (None, "L0")
                 else find_audio(AUDIO_DEGRADED / level, stem))
        if level == "L0" and audio is None:
            audio = find_audio(AUDIO_DEGRADED / "L0", stem)
        if audio:
            st.audio(str(audio))
        else:
            st.info("El audio no está en este equipo: los audios no se suben al repo (ver README). "
                    "La transcripción sí está en el cache.")
        st.markdown("**Registro esperado** (ground truth)")
        expected = {k: v for k, v in gt[stem].items() if k not in ("evidencia", "trampas")}
        st.json(expected, expanded=True)
        if dataset == "llamadas" and gt[stem].get("trampas"):
            st.markdown("**Trampas del guion**")
            st.dataframe(pd.DataFrame(gt[stem]["trampas"]), hide_index=True, use_container_width=True)
    with right:
        data = cached_transcript(dataset, stem, level)
        if data is None:
            st.warning("No hay transcripción cacheada para este audio.")
        else:
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Duración", "{}:{:02d}".format(*divmod(round(data["audio_duration_s"]), 60)))
            m2.metric("Dispositivo", data["runtime_device"])
            m3.metric("Tiempo de transcripción", f"{data['transcribe_s']:.1f} s")
            m4.metric("GPU", data.get("gpu_name") or "—")
            st.text_area("Transcripción", data["text"], height=260)
            with st.expander("Segmentos con tiempo"):
                st.dataframe(pd.DataFrame(data["segments"]), hide_index=True, use_container_width=True)

# ---------------------------------------------------------------- 3. Resultados (Tarea 1)
with tab_results:
    st.subheader("Capa 1 · Calidad de transcripción: modelo × dispositivo × precisión")
    bench = read_csv("benchmark_entrevistas.csv")
    if bench is None:
        st.info("Corre `python scripts/transcribe.py --set entrevistas`.")
    else:
        group = ["model", "runtime_device", "compute_type"]
        summary = (bench.groupby(group)[["wer", "cer", "transcribe_s", "rtf", "vram_peak_mib"]]
                   .mean().reset_index())
        summary["config"] = summary[group].astype(str).agg(" / ".join, axis=1)
        st.caption("CPU: PC local (i5-6200U, 2 núcleos). GPU: Colab, Tesla T4. "
                   "La VRAM solo se mide en GPU.")
        st.dataframe(
            summary[["config", "wer", "cer", "transcribe_s", "rtf", "vram_peak_mib"]].rename(columns={
                "config": "modelo / dispositivo / precisión", "transcribe_s": "tiempo (s)",
                "vram_peak_mib": "VRAM pico (MiB)"}),
            hide_index=True, use_container_width=True,
            column_config={"wer": st.column_config.NumberColumn(format="%.3f"),
                           "cer": st.column_config.NumberColumn(format="%.3f"),
                           "tiempo (s)": st.column_config.NumberColumn(format="%.1f"),
                           "rtf": st.column_config.NumberColumn(format="%.3f"),
                           "VRAM pico (MiB)": st.column_config.NumberColumn(format="%.0f")},
        )
        metric = st.radio("Gráfico", ["wer", "transcribe_s"], horizontal=True,
                          format_func={"wer": "WER", "transcribe_s": "Tiempo por audio (s)"}.get)
        st.bar_chart(summary, x="config", y=metric, horizontal=True)
        with st.expander("Detalle por audio"):
            st.dataframe(bench, hide_index=True, use_container_width=True)

    st.subheader("Capa 2 · Calidad del registro: reglas vs. LLM")
    ext = read_csv("extraction.csv")
    if ext is None:
        st.info("Corre `python scripts/extract_interviews.py`.")
    else:
        totals = ext.groupby("metodo").agg(exactitud=("correcto", "mean"),
                                           sin_verificar=("estado", lambda s: int((s == "sin_verificar").sum())),
                                           campos=("estado", "size"))
        cols = st.columns(len(totals))
        for col, (method, row) in zip(cols, totals.iterrows()):
            col.metric(f"Exactitud · {method}", pct(row.exactitud),
                       help=f"{row.sin_verificar} de {row.campos} valores quedaron sin_verificar")
        st.dataframe(ext.groupby(["campo", "metodo"])["correcto"].mean().unstack().map(pct),
                     use_container_width=True)
        details = read_json(RESULTS / "extraction.json") or {}
        if details:
            audio_id = st.selectbox("Ver el registro de una entrevista", list(details))
            cols = st.columns(len(details[audio_id]))
            for col, (method, verified) in zip(cols, details[audio_id].items()):
                with col:
                    st.markdown(f"**{method}**")
                    st.dataframe(fields_table(verified), hide_index=True, use_container_width=True)

    ci, record, glossary = read_csv("extraction_ci.csv"), read_csv("record_metrics.csv"), read_csv("glossary_summary.csv")
    if ci is not None:
        with st.expander("Intervalos de confianza (Wilson, 95 %) y métricas del registro"):
            st.caption("Con 5 entrevistas por campo los intervalos son anchos: la muestra no separa un campo de otro.")
            st.dataframe(ci, hide_index=True, use_container_width=True)
            if record is not None:
                st.dataframe(record, hide_index=True, use_container_width=True)

    wvr = read_csv("wer_vs_record.csv")
    if wvr is not None:
        st.subheader("¿El WER dice si el registro sirve?")
        st.caption("Cada punto es una entrevista: WER de su transcripción contra el acierto del registro del LLM.")
        st.scatter_chart(wvr, x="wer", y="acierto_llm")
        st.dataframe(wvr.drop(columns="set"), hide_index=True, use_container_width=True)

    if glossary is not None:
        st.subheader("Glosario de dominio")
        st.caption("Misma config (small / cpu / int8), sin glosario contra hotwords e initial_prompt. "
                   "dif_wer_vs_sin < 0 = el glosario ayudó; IC por bootstrap sobre los clips.")
        st.dataframe(glossary, hide_index=True, use_container_width=True)

# ---------------------------------------------------------------- 4. Pedidos (Tarea 2)
with tab_orders:
    st.subheader(f"Captura de pedidos · {cfg['calls']['domain']}")
    deg, bench_calls = read_csv("degradation.csv"), read_csv("benchmark_llamadas.csv")
    val, traps = read_csv("calls_validation.csv"), read_csv("traps.csv")
    if val is None or traps is None:
        st.info("Corre `scripts/degrade.py`, `scripts/transcribe.py --set llamadas` y `scripts/validate_calls.py`.")
    else:
        st.markdown("**Escalera de degradación y las dos capas de métricas por nivel**")
        ladder = pd.DataFrame({"nivel": list(LEVEL_NAMES)}).set_index("nivel")
        ladder["descripción"] = [LEVEL_NAMES[lv].split(" · ")[1] for lv in ladder.index]
        if deg is not None:
            ladder["SNR vs. nivel anterior (dB)"] = deg.groupby("level")["snr_vs_anterior_db"].mean().round(1)
        if bench_calls is not None:
            ladder[["WER", "CER"]] = bench_calls.groupby("level")[["wer", "cer"]].mean().map(pct)
        caught = traps.groupby("level")["detectada"].agg(["sum", "count"])
        ladder["trampas detectadas"] = caught["sum"].astype(int).astype(str) + "/" + caught["count"].astype(str)
        st.dataframe(ladder.fillna("—"), use_container_width=True)
        calls_ci = read_csv("calls_ci.csv")
        if calls_ci is not None:
            st.caption("Capa del registro por nivel, con IC de Wilson (95 %)")
            st.dataframe(calls_ci, hide_index=True, use_container_width=True)

        st.markdown("**Trampas: detectadas vs. no detectadas**")
        pivot = traps.pivot_table(index=["llamada", "trampa", "tipo"], columns="level",
                                  values="detectada", aggfunc="first")
        st.dataframe(pivot.map(lambda v: "✔ detectada" if v else "✘ no detectada"), use_container_width=True)
        by_type = traps.groupby(["tipo", "level"])["detectada"].sum().unstack().astype(int)
        st.caption("Detectadas por tipo de trampa y nivel")
        st.dataframe(by_type, use_container_width=True)

        st.markdown("**Validación aritmética y clasificación del error**")
        st.dataframe(val, hide_index=True, use_container_width=True)
        orders = read_json(RESULTS / "orders.json") or {}
        if orders:
            key = st.selectbox("Ver el pedido extraído", list(orders))
            st.json(orders[key], expanded=False)

# ---------------------------------------------------------------- 5. Probador
with tab_tester:
    st.subheader("Sube un audio y obtén el registro")
    st.caption("Llama a `engine.pipeline.process_audio`. Sin GPU usa la CPU (int8); "
               "la extracción con LLM necesita Ollama corriendo.")
    upload = st.file_uploader("Audio", type=[e.strip(".") for e in AUDIO_EXT])
    c1, c2, c3 = st.columns(3)
    kind = c1.radio("Tipo", ["entrevista", "llamada"], horizontal=True)
    method = c2.radio("Extracción", ["llm", "reglas"], horizontal=True, disabled=kind == "llamada")
    ref_date = c3.date_input("Fecha de la grabación", date(2026, 10, 29))
    model = st.selectbox("Modelo Whisper", cfg["asr"]["models"], index=0,
                         help="small es ~3 veces más rápido en CPU")

    if upload and st.button("Procesar", type="primary"):
        from engine.pipeline import process_audio

        with tempfile.NamedTemporaryFile(suffix=Path(upload.name).suffix, delete=False) as tmp:
            tmp.write(upload.read())
        with st.spinner("Transcribiendo y extrayendo..."):
            st.session_state["tester"] = process_audio(tmp.name, kind=kind,
                                                       method="llm" if kind == "llamada" else method,
                                                       ref_date=ref_date, model=model)

    res = st.session_state.get("tester")
    if res:
        if res["error"]:
            st.error(res["error"])
        m1, m2, m3 = st.columns(3)
        m1.metric("Dispositivo", res["device"] or "—")
        m2.metric("Transcripción", f"{res['transcribe_s']:.1f} s" if res["transcribe_s"] else "—")
        m3.metric("Tiempo total", f"{res['elapsed_s']:.1f} s")
        if res["transcript"]:
            st.text_area("Transcripción", res["transcript"], height=180)
        if res["verified"]:
            st.markdown("**Registro** (cada valor se busca literalmente en la transcripción)")
            st.dataframe(fields_table(res["verified"]), hide_index=True, use_container_width=True)
        if res["validation"]:
            v = res["validation"]
            st.markdown("**Validación aritmética**")
            if v["cuadra"]:
                st.success(f"El total cuadra: {v['total_calculado']:g}")
            else:
                st.warning(f"No cuadra: calculado {v['total_calculado']:g}, dicho {v['total_dicho']}")
            st.json(res["fields"], expanded=False)
