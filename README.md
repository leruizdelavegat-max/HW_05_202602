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

## Corpus

- **Tarea 1:** 5 entrevistas de trabajo inventadas, con los seis campos dichos de forma poco limpia
  y en un orden distinto en cada una.
- **Tarea 2:** dominio **restaurante** (delivery). 5 llamadas con productos, tamaños, precios, una
  promoción, dirección, forma de pago y un total dicho en voz alta: 3 autocorrecciones, 3 totales
  erróneos y 5 direcciones con dígitos.

Los guiones, el detalle de cómo se varió cada campo y la tabla de trampas están en
[`docs/guiones/`](docs/guiones/README.md).

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

Requisitos: Python 3.12. No hace falta instalar ffmpeg: PyAV (fijado en `requirements.txt`) trae
sus librerías para leer audio y para la compresión Opus del nivel L1.

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

La extracción con LLM usa por defecto un modelo **local y gratuito** con [Ollama](https://ollama.com)
(no requiere API key):

```bash
winget install Ollama.Ollama
ollama pull qwen2.5:3b
```

`qwen2.5:3b` ocupa ~2 GB y cabe en 8 GB de RAM. Para usar Claude en su lugar, cambia
`extraction.llm.provider` a `anthropic` en `config.yaml` y copia `.env.example` a `.env` con tu
`ANTHROPIC_API_KEY`.

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

Este equipo no tiene GPU NVIDIA, así que las combinaciones `cuda` se corren en Colab con
[`notebooks/colab_gpu.ipynb`](notebooks/colab_gpu.ipynb):

1. Entorno de ejecución → Cambiar tipo → **T4 GPU**.
2. El notebook clona el repo, instala `requirements.txt` y pide subir `audios_colab.zip` (los audios no están en GitHub).
3. Corre la degradación, `transcribe.py --set entrevistas --device cuda` y `transcribe.py --set llamadas`.
4. Descarga `resultados_gpu.zip`; su contenido (`cache/transcripts/` y `results/`) se copia al repo local.

Cada JSON del cache guarda `runtime_device` (lo que reporta CTranslate2 en ejecución), `gpu_name`
y `vram_peak_mib` (medido con NVML), que son la prueba de uso de la GPU.

## Resultados

Los números salen de `results/*.csv`; las transcripciones que los generan están en `cache/transcripts/`.

### Referencias: cómo se construyeron (y su sesgo)

Las referencias para WER/CER empiezan siendo el guion, pero al grabar no se lee palabra por palabra.
`scripts/diff_references.py` compara el guion con dos transcripciones de modelos distintos y marca
los tramos donde **ambos** modelos se apartan del guion de la misma forma: ahí casi seguro se dijo
otra cosa, y la referencia toma lo que se dijo. Las excepciones (errores ortográficos del ASR, como
«peperoni» o «mustaza», y los tramos escuchados) están en `data/references/revisiones.json`.

- Entrevistas: se contrastaron `medium/cpu/int8` y `small/cpu/int8`.
- Llamadas (nivel L0): `medium/cuda/float16` y `small/cpu/int8`.

**Sesgo declarado:** los modelos que se usaron para corregir las referencias quedan favorecidos.
En las entrevistas eso beneficia a las combinaciones int8 (por eso medium/int8 sale con 1.4 % y
medium/float32 con 4.2 %); la diferencia entre precisiones hay que leerla con esa cautela. La
comparación CPU vs. GPU a igual precisión no se ve afectada.

### Tarea 1 · ASR: modelo × dispositivo × precisión

Promedio de las 5 entrevistas (3:34 a 3:57 min cada una). Tiempo = solo inferencia, por audio.
RTF = tiempo / duración del audio (menos de 1 = más rápido que tiempo real).

| Modelo | Dispositivo | Precisión | WER | CER | Tiempo (s) | RTF | VRAM pico (MiB) |
|---|---|---|---|---|---|---|---|
| small | CPU | int8 | 3.4 % | 1.4 % | 158 | 0.72 | – |
| small | CPU | float32 | 3.2 % | 1.4 % | 280 | 1.27 | – |
| small | GPU | int8_float16 | 3.5 % | 1.4 % | 5.8 | 0.026 | 3 505 |
| small | GPU | float16 | 3.5 % | 1.5 % | 6.0 | 0.027 | 3 446 |
| medium | CPU | int8 | 1.4 % | 0.8 % | 476 | 2.16 | – |
| medium | CPU | float32 | 4.2 % | 3.3 % | 819 | 3.70 | – |
| medium | GPU | int8_float16 | 1.5 % | 0.9 % | 11.5 | 0.052 | 4 270 |
| medium | GPU | float16 | 4.2 % | 3.3 % | 11.4 | 0.052 | 4 102 |

- **CPU:** PC local, Intel Core i5-6200U (2 núcleos), 8 GB de RAM, sin GPU NVIDIA.
- **GPU:** Google Colab, Tesla T4. Cada JSON del cache guarda `runtime_device: cuda`, `gpu_name` y
  `vram_peak_mib` como prueba.

Interpretación:

- **Misma calidad en CPU y GPU a igual precisión.** medium float32 (CPU) y float16 (GPU) dan el mismo
  4.2 %; int8 e int8_float16, 1.4 % y 1.5 %. La GPU no cambia el resultado, solo el tiempo.
- **La GPU es 40 a 70 veces más rápida.** medium tarda 13.6 min por entrevista en float32 en esta CPU
  (no sirve para uso en tiempo real) y 11 s en la T4. int8 casi duplica la velocidad en CPU sin perder
  calidad; en GPU, int8_float16 apenas cambia el tiempo.
- **medium float16/float32 se salta oraciones.** En entrevista_03 omitió dos oraciones completas,
  entre ellas «en realidad mi inglés es básico» (justo la evidencia de un campo), y en entrevista_05
  insertó una frase que nadie dijo. Por eso su WER sube a 8.8 % y 6.5 % en esos audios. Es el modo de
  falla típico de Whisper: no confunde palabras, borra o inventa tramos enteros.
- **Para producción** elegiríamos medium int8_float16 en GPU (mejor WER, 11 s por audio) y small int8
  si solo hay CPU (RTF 0.72, ~3 % de WER).

### Tarea 1 · Extracción: reglas vs. LLM

Sobre la transcripción por defecto (`medium/cuda/float16`), 5 entrevistas × 6 campos. LLM local:
`qwen2.5:3b` vía Ollama, con salida restringida a un JSON Schema.

| Campo | Reglas | LLM |
|---|---|---|
| Años de experiencia | 40 % | 80 % |
| Último puesto | 0 % | 100 % |
| Tecnologías | 60 % | 80 % |
| Expectativa salarial | 20 % | 100 % |
| Disponibilidad (fecha) | 40 % | 80 % |
| Nivel de inglés | 0 % | 80 % |
| **Total** | **27 %** | **87 %** |
| Valores `sin_verificar` | 20 de 30 | 4 de 30 |

- Los guiones se escribieron para que las reglas fallen: autocorrecciones («cuatro, perdón, tres»),
  cifras con contexto («programo desde el dos mil dieciocho»), dos cargos o dos niveles de inglés que
  se contradicen. Las reglas toman el primer patrón que encuentran; el LLM entiende la corrección.
- **Regla de evidencia literal:** cada valor debe aparecer en la transcripción; si no, queda
  `sin_verificar`. Atrapó al LLM cuando inventó: en una primera corrida devolvió «inmediata» como
  disponibilidad en 3 entrevistas (copiaba un ejemplo del prompt); los 3 quedaron `sin_verificar`. Se
  corrigió el prompt para pedir la frase literal.
- **Fechas:** la disponibilidad se dice en relativo («el lunes mismo», «necesitaría un mes») y se
  guarda como fecha absoluta desde la fecha de la entrevista (2026-10-29). El modelo de 3B fallaba esa
  aritmética, así que el LLM extrae la frase y la fecha la calcula `engine/dates.py`, el mismo código
  que usan las reglas.
- **Errores que quedan en el LLM:** años de experiencia de entrevista_02 (exige restar 2026 − 2018);
  nivel de inglés de entrevista_03, cuya evidencia («mi inglés es básico») no está en la transcripción
  porque el ASR la borró (ver arriba); y tecnologías de entrevista_05 (omitió pandas).

### Tarea 2 · Escalera de degradación

Escalera acumulativa (cada nivel parte del anterior), determinista (semilla 42):

| Nivel | Qué simula | SNR vs. L0 | SNR vs. nivel anterior |
|---|---|---|---|
| L0 | Grabación original (16 kHz) | – | – |
| L1 | Nota de voz de WhatsApp: Opus a 16 kbps | 14.9 dB | 14.9 dB |
| L2 | Línea telefónica: 8 kHz, banda 300–3400 Hz | 7.5 dB | 8.1 dB |
| L3 | Ruido de fondo a 10 dB sobre la señal de L2 | 6.0 dB | 10.0 dB |

**Por qué 10 dB en L3:** 10 dB significa que la voz tiene 10 veces la potencia del ruido. Es el nivel
de una llamada hecha desde la calle o desde un local con gente: se entiende sin esfuerzo, pero el ruido
se oye todo el tiempo. Por encima de 20 dB el ruido apenas afecta a Whisper; por debajo de 5 dB ya no
representa una llamada normal de pedido sino un caso extremo. 10 dB es el punto realista más exigente.
El SNR se mide sobre el audio generado (columna `snr_vs_anterior_db` de `results/degradation.csv`).

### Tarea 2 · Las dos capas de métricas por nivel

Transcripción con `medium/cuda/float16`; extracción con `qwen2.5:3b`. 11 trampas: 3 autocorrecciones,
3 totales erróneos y 5 direcciones con dígitos.

| Nivel | WER | CER | Trampas detectadas | Autocorrecciones | Totales erróneos | Direcciones |
|---|---|---|---|---|---|---|
| L0 | 7.5 % | 4.6 % | 11/11 | 3/3 | 3/3 | 5/5 |
| L1 | 6.2 % | 3.5 % | 11/11 | 3/3 | 3/3 | 5/5 |
| L2 | 6.3 % | 2.9 % | 11/11 | 3/3 | 3/3 | 5/5 |
| L3 | 10.4 % | 5.0 % | 10/11 | 3/3 | 3/3 | 4/5 |

- **El WER no siempre sube con la degradación.** L0 sale peor que L1 por una alucinación: en
  llamada_01 (L0) Whisper repitió un bloque de ~20 s («paga en efectivo o con tarjeta… llegan a las
  9»). Con 5 llamadas, un solo episodio así mueve el promedio. El salto real llega con el ruido (L3).
- **Más WER no implica perder el dato.** Aun con 10.4 % de WER en L3 se detectan 10 de 11 trampas: los
  errores caen en muletillas y palabras de relleno, no en cantidades ni precios. La única trampa perdida
  es la dirección de llamada_03 en L3.
- **El registro completo es más frágil que las trampas.** El modelo de 3B parte un ítem en dos (gaseosa
  de cola + gaseosa de naranja), mete el tamaño dentro del nombre del producto o agrega un producto que
  solo se ofreció (mazamorra). La promoción sale bien en el 100 % de los casos y la forma de pago en el
  60–80 %. Un LLM más grande mejoraría esta capa; la verificación y la aritmética no cambian.

### Tarea 2 · Error del ASR vs. error del hablante

Regla (`engine/validate.py::classify_error`): se transcribe la misma llamada en L0–L3 y se compara el
total dicho.

- Si el **total dicho es el mismo en todos los niveles** y no cuadra con Σ(cantidad × precio) −
  promoción → **error del hablante**: lo dijo mal, y por eso se transcribe igual sin importar la calidad
  del audio.
- Si el **total dicho cambia entre niveles** → **error del ASR**: depende de la calidad del audio.
- Si todos cuadran → sin error.

Resultado: los 3 totales erróneos (llamadas 01, 03 y 04) se clasifican como error del hablante, y la
llamada de control (05) como sin error. Hubo un falso positivo: llamada_02 dice bien su total (100),
pero en L0 el LLM agregó un producto que no se pidió, el total calculado no cuadró y la llamada se
marcó como error del hablante. La regla depende de que la extracción de ítems sea correcta.

### Limitaciones

- Las direcciones de las llamadas usan nombres de calles reales de Lima con números inventados; no
  corresponden a ninguna persona.
- La parte final de llamada_03 no se grabó; su referencia refleja lo que sí se dijo (3:08 min).
- 5 audios por tarea: los promedios se mueven con un solo caso (ver la alucinación de llamada_01).
