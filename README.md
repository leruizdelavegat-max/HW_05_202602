# HW_05_202602 · De la voz al registro

Pipeline que convierte entrevistas de trabajo y llamadas de venta grabadas en registros estructurados
y verificables. Usa Whisper (faster-whisper) para la transcripción, reglas y un LLM para la extracción,
y validación aritmética para los pedidos.

- **Documento del pipeline (público):** TODO enlace a Notion / Miro
- **Video (≤ 8 min):** TODO enlace

## Declaración de audio y consentimiento

TODO: confirma con tus palabras que grabaste todos los audios tú, que apareces en todos, que el
contenido es inventado y que todas las personas grabadas dieron su consentimiento. Los audios no se
suben al repo, solo sus transcripciones cacheadas en `cache/transcripts/`.

## Herramientas de IA declaradas

TODO: lista los agentes de IA (por ejemplo Claude Code) y los servidores MCP que usaste, y para qué.

## Estructura

```
config.yaml              Configuración única: modelos, grid ASR, campos, escalera de degradación
engine/                  Motor compartido por ambas tareas
  asr.py                 Transcripción + tiempo, dispositivo reportado por el runtime y pico de VRAM
  metrics.py             WER / CER con normalización común
  numbers.py             "seis mil quinientos" -> 6500
  extract_rules.py       Extractor por reglas (regex)
  extract_llm.py         Extractor con LLM (salida JSON con esquema)
  verify.py              Regla de evidencia literal -> `sin_verificar`
  degrade.py             Escalera L0-L3
  validate.py            Σ(cantidad × precio) − promoción = total; error ASR vs. hablante
scripts/                 Pasos del pipeline (ver abajo)
app.py                   App de Streamlit (4 pestañas)
data/ground_truth/       Campos esperados por audio
data/references/         Transcripciones manuales para WER/CER
cache/transcripts/       Transcripciones cacheadas (se versionan)
results/                 CSV y JSON generados
```

## Instalación

Requisitos: Python 3.12 y [ffmpeg](https://ffmpeg.org/) en el PATH.

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env   # y completa ANTHROPIC_API_KEY
```

## Cómo correr el pipeline

1. Copia tus audios a `data/audio/entrevistas/` y `data/audio/llamadas/` (por ejemplo `entrevista_01.m4a`).
2. Escribe las referencias en `data/references/` y el ground truth en `data/ground_truth/`.
3. Corre los pasos:

```bash
python scripts/transcribe.py --set entrevistas
python scripts/extract_interviews.py
python scripts/degrade.py
python scripts/transcribe.py --set llamadas
python scripts/validate_calls.py
streamlit run app.py
```

Cada transcripción se cachea en `cache/transcripts/`; si vuelves a correr un paso, no se recalcula.

Pruebas del motor y de la app (no requieren GPU, audio ni API key):

```bash
python -m pytest -q tests
```

### Comparación con GPU (Google Colab)

Este equipo no tiene GPU NVIDIA, así que las combinaciones `cuda` del grid se corren en Colab:

1. Entorno de ejecución → Cambiar tipo → **T4 GPU**.
2. Sube el repo (o clónalo) y los audios de `data/audio/`.
3. `!apt-get install -y ffmpeg && pip install -r requirements.txt`
4. `!python scripts/transcribe.py --set entrevistas` y `!python scripts/transcribe.py --set llamadas`
5. Descarga `cache/transcripts/` y `results/` y cópialos al repo local.

Cada JSON del cache guarda `runtime_device` (lo que reporta CTranslate2 en ejecución), `gpu_name`
y `vram_peak_mib` (medido con NVML), que son la prueba de uso de la GPU.

## Resultados

TODO: tabla de WER / CER / tiempo / VRAM por modelo, dispositivo y precisión, con tu interpretación.

TODO: exactitud de extracción por campo (reglas vs. LLM) y cuántos valores quedaron `sin_verificar`.

TODO: escalera de degradación. Justifica el SNR elegido para L3 (10 dB por defecto, aproximadamente
una conversación en un lugar con ruido de fondo moderado) y reporta las dos capas de métricas por nivel:
WER/CER y trampas detectadas.

TODO: regla para distinguir error del ASR de error del hablante (ver `engine/validate.py`) y trampas
detectadas vs. no detectadas.
