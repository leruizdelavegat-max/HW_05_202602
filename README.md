# HW_05_202602 · De la voz al registro

Pipeline que convierte entrevistas de trabajo y llamadas de venta grabadas en registros estructurados
y verificables. Usa Whisper (faster-whisper) para la transcripción, reglas y un LLM para la extracción,
y validación aritmética para los pedidos.

- **Documento del pipeline (público):** TODO enlace a Notion / Miro
- **Video (≤ 8 min):** TODO enlace

## Declaración de audio y consentimiento

- Grabé yo los 10 audios del corpus (5 entrevistas y 5 llamadas) y aparezco en todos como una de las
  dos voces.
- **Todo lo que se dice es inventado:** los candidatos, cargos, salarios, pedidos, precios y formas de
  pago no corresponden a ninguna persona real. Las direcciones usan nombres de calles de Lima con
  números inventados.
- **Consentimiento:** la persona que grabó conmigo dio su consentimiento para aparecer en los audios y
  en el video. No se la nombra en este repositorio.
- Los audios no se suben al repo, solo sus transcripciones cacheadas en `cache/transcripts/`. Para
  regenerar los resultados se pueden solicitar abriendo un issue en este repositorio.

## Corpus

- **Tarea 1:** 5 entrevistas de trabajo inventadas, con los seis campos dichos de forma poco limpia
  y en un orden distinto en cada una.
- **Tarea 2:** dominio **restaurante** (delivery). 5 llamadas con productos, tamaños, precios, una
  promoción, dirección, forma de pago y un total dicho en voz alta: 3 autocorrecciones, 3 totales
  erróneos y 5 direcciones con dígitos.

Los guiones, el detalle de cómo se varió cada campo y la tabla de trampas están en
[`docs/guiones/`](docs/guiones/README.md).

## Herramientas de IA declaradas

| Herramienta | Tipo | Para qué se usó |
|---|---|---|
| Claude Code (app de escritorio, modelo Claude Opus) | Agente de código | Estructura del repo, código del motor, scripts, pruebas, app y redacción del README. Cada resultado se revisó y corrió en local |
| `Claude_Browser` (navegador integrado de Claude Code) | Servidor MCP | Abrir la app de Streamlit en local y comprobar que cada pestaña carga sin errores |
| Ollama + `qwen2.5:3b` | LLM local del pipeline (no es un agente) | Extracción de campos con salida JSON, sin API key y sin enviar datos fuera del equipo |

No se usaron otros servidores MCP. Ningún agente generó audio ni ground truth: los audios los grabé yo
y las referencias se corrigieron contra lo que se dijo en cada grabación.

## Estructura

```
config.yaml              Configuración única: modelos, grid ASR, campos, escalera de degradación
engine/                  Motor compartido por ambas tareas (sin librerías de interfaz)
  pipeline.py            process_audio(ruta) -> transcripción, campos, verificación, dispositivo,
                         tiempo y error. Es lo único que llama el probador de la app
  asr.py                 Transcripción + tiempo, dispositivo reportado por el runtime y pico de VRAM
  metrics.py             WER / CER con normalización común
  numbers.py             "seis mil quinientos" -> 6500
  extract_rules.py       Extractor por reglas (regex)
  extract_llm.py         Extractor con LLM (salida JSON con esquema)
  verify.py              Regla de evidencia literal -> `sin_verificar`
  degrade.py             Escalera L0-L3
  validate.py            Σ(cantidad × precio) − promoción = total; error ASR vs. hablante
scripts/                 Pasos del pipeline (ver abajo)
app.py                   App de Streamlit: problema y método, corpus (audio + transcripción),
                         resultados (dos capas), pedidos (escalera, validación, trampas) y probador
data/ground_truth/       Campos esperados por audio
data/references/         Transcripciones manuales para WER/CER
cache/transcripts/       Transcripciones cacheadas (se versionan)
results/                 CSV y JSON generados
```

### Un motor, dos tareas

`engine.pipeline.process_audio(ruta, kind=...)` es la única función que recibe un audio nuevo y
devuelve transcripción, campos, verificación, dispositivo, tiempo y error. Sirve a los dos esquemas
de registro cambiando solo el extractor:

| Paso | Entrevista (`kind="entrevista"`) | Llamada (`kind="llamada"`) |
|---|---|---|
| Transcripción | `engine/asr.py` | `engine/asr.py` (la misma) |
| Extracción | `extract_interview` + `INTERVIEW_SCHEMA` | `extract_order` + `ORDER_SCHEMA` |
| Prompt | `extraction.llm.prompts.entrevista` en `config.yaml` | `extraction.llm.prompts.pedido` |
| Verificación literal | `engine/verify.py` | `engine/verify.py` (la misma) |
| Validación | – | `engine/validate.py` (aritmética + error ASR vs. hablante) |

Los scripts por lotes (`extract_interviews.py`, `validate_calls.py`) usan esas mismas funciones del
motor sobre las transcripciones cacheadas, para no volver a transcribir.

Comando para comprobar que el motor no importa ninguna librería de interfaz (imprime `[]`):

```bash
python -c "import sys, engine.pipeline; print([m for m in sys.modules if m.split('.')[0] in ('streamlit', 'altair', 'gradio', 'plotly')])"
```

`tests/test_app.py` comprueba además que `app.py` solo importa `engine.config` y `engine.pipeline`.

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
python scripts/glossary.py
python scripts/report.py
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

**Normalización antes de comparar** (`engine/metrics.py::normalize_text`, igual para referencia e
hipótesis): minúsculas, números en palabras a dígitos («seis mil quinientos» → 6500), sin tildes, sin
separador de miles (6.500 → 6500), sin puntuación y espacios simples.

**IC 95 %:** bootstrap de percentiles remuestreando los 5 clips con reemplazo (10 000 remuestreos,
semilla 42; `results/asr_ci.csv`). Con 5 clips el intervalo es ancho: sirve para ver qué diferencias
no se distinguen del azar, no para dar una cifra precisa.

| Modelo | Dispositivo | Precisión | WER [IC 95 %] | CER | Tiempo (s) | RTF | VRAM pico (MiB) |
|---|---|---|---|---|---|---|---|
| small | CPU | int8 | 3.4 % [2.9–3.9] | 1.4 % | 158 | 0.72 | – |
| small | CPU | float32 | 3.2 % [2.7–3.8] | 1.4 % | 280 | 1.27 | – |
| small | GPU | int8_float16 | 3.5 % [3.0–4.1] | 1.4 % | 5.8 | 0.026 | 3 505 |
| small | GPU | float16 | 3.5 % [3.2–3.8] | 1.5 % | 6.0 | 0.027 | 3 446 |
| medium | CPU | int8 | 1.4 % [0.8–1.8] | 0.8 % | 476 | 2.16 | – |
| medium | CPU | float32 | 4.2 % [1.7–6.9] | 3.3 % | 819 | 3.70 | – |
| medium | GPU | int8_float16 | 1.5 % [0.9–2.0] | 0.9 % | 11.5 | 0.052 | 4 270 |
| medium | GPU | float16 | 4.2 % [1.7–6.9] | 3.3 % | 11.4 | 0.052 | 4 102 |

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

### Tarea 1 · Glosario de dominio

**Qué mecanismo hay y en qué versión.** En `faster-whisper` 1.1.1 (la versión fijada) `transcribe()`
acepta dos: `initial_prompt` (existe desde la primera versión, igual que en `openai-whisper`) y
`hotwords` (agregado en `faster-whisper` 1.0; no existe en `openai-whisper`). Leyendo el código de la
versión instalada (`WhisperModel.get_prompt`): `hotwords` se antepone a **cada** ventana de 30 s y se
ignora si se pasa `prefix`; `initial_prompt` solo entra en la **primera** ventana, después la
reemplaza el texto ya transcrito. La documentación que circula los mezcla, por eso se midieron los dos.

Misma config que el baseline (small / cpu / int8, 5 entrevistas); glosario en `asr.glossary` de
`config.yaml` (tecnologías y cargos). `python scripts/glossary.py` → `results/glossary*.csv`.

| Variante | WER [IC 95 %] | Diferencia de WER vs. sin glosario [IC 95 %] | Términos del glosario bien transcritos [IC 95 %] |
|---|---|---|---|
| Sin glosario | 3.4 % [2.9–3.9] | – | 18/22 · 82 % [62–93] |
| `hotwords` | 4.2 % [3.1–6.0] | +0.8 pp [−0.5, +2.9] | 22/22 · 100 % [85–100] |
| `initial_prompt` | 3.4 % [3.0–3.8] | 0.0 pp [−0.4, +0.3] | 21/22 · 95 % [78–99] |

- **El glosario arregla justo las palabras que importan para el registro.** Sin glosario se perdieron
  «Power BI», «AWS», «Tableau» y «Azure» (una por entrevista): son valores del campo `tecnologias`.
  Con `hotwords` salen las 4; con `initial_prompt`, 3 de 4 (sigue fallando «AWS»).
- **El WER casi no lo ve.** 4 palabras en ~2 000 no mueven el promedio; ningún IC de la diferencia
  excluye el cero. Es otro ejemplo de por qué el WER solo no sirve para juzgar el registro.
- **`hotwords` tiene un costo:** en entrevista_03 el WER sube de 2.9 % a 7.6 % porque el modelo se
  saltó una oración entera («me gusta tener tareas claras…»). Es el mismo modo de falla de borrar
  tramos que se ve en medium float16. Con 5 clips no se puede saber si es sistemático.
- **Decisión:** `initial_prompt` gana casi todo el beneficio sin el riesgo de borrar texto. No se activó
  en el pipeline por defecto porque la extracción y sus métricas ya estaban calculadas sin glosario;
  queda medido y listo para activarse.

### Tarea 1 · Extracción: reglas vs. LLM

Sobre la transcripción por defecto (`medium/cuda/float16`), 5 entrevistas × 6 campos. LLM local:
`qwen2.5:3b` vía Ollama, con salida restringida a un JSON Schema.

| Campo | Reglas | LLM |
|---|---|---|
| Años de experiencia | 40 % | 80 % |
| Último puesto | 0 % | 100 % |
| Tecnologías | 60 % | 80 % |
| Pretensión salarial | 20 % | 100 % |
| Disponibilidad (fecha) | 40 % | 80 % |
| Nivel de inglés | 0 % | 80 % |
| **Total [IC 95 % de Wilson]** | **27 % [14–44]** | **87 % [70–95]** |
| Valores `sin_verificar` | 20 de 30 · 67 % [49–81] | 4 de 30 · 13 % [5–30] |

Cada campo tiene solo 5 observaciones: un 80 % por campo tiene un IC de 38–96 %
(`results/extraction_ci.csv`). La muestra separa el total del LLM del de las reglas, pero no un campo
de otro.

Métricas propias de cada tipo de campo (`results/record_metrics.csv`):

| Métrica | Reglas | LLM |
|---|---|---|
| F1 macro de `nivel_ingles` (clases básico / intermedio / avanzado) | 0.00 | 0.67 |
| Error absoluto medio de `anios_experiencia` | 0 años (solo 2 de 5 extraídos) | 0.8 años (5 de 5; un error de 4) |
| Error absoluto medio de `pretension_salarial` | 4 196 soles (1 de 4 extraído) | 0 soles (4 de 4) |

El error de las reglas en el salario muestra la asimetría entre tipos de campo: en «cuatro mil
doscientos» la regla capturó «4» y se quedó corta por 4 196 soles. En un campo categórico, un error
cambia una clase por otra; en un numérico, un dígito perdido es un error de miles.

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

### ¿Se puede saber si el registro sirve mirando solo el WER?

No. WER de cada entrevista (`medium/cuda/float16`, la transcripción que usa la extracción) contra el
acierto del registro del LLM (`results/wer_vs_record.csv`):

| Entrevista | WER | Campos correctos | Qué falló |
|---|---|---|---|
| entrevista_01 | **1.2 %** (el más bajo) | 5/6 | disponibilidad: 15 de noviembre en vez del 13 |
| entrevista_04 | 1.7 % | 6/6 | – |
| entrevista_02 | 2.7 % | 5/6 | años de experiencia: 4 en vez de 8 |
| entrevista_05 | 6.5 % | 5/6 | tecnologías: omitió pandas |
| entrevista_03 | **8.8 %** (el más alto) | 5/6 | nivel de inglés (el ASR borró la frase) |

- **WER bajo, registro roto:** entrevista_01 tiene la mejor transcripción del corpus y aun así guarda
  una fecha de inicio equivocada. entrevista_02 (2.7 %) guarda 4 años de experiencia en vez de 8: el
  ASR transcribió bien «desde el dos mil dieciocho» y el error está en la resta.
- **WER alto, registro casi entero:** entrevista_03 tiene 7 veces el WER de entrevista_01 y aun así
  saca bien los dos campos más frágiles: el salario (4 200) y los años con autocorrección («cuatro,
  perdón, tres»). Ningún clip del corpus tiene WER alto y registro perfecto. El más cercano está en
  las llamadas: llamada_01 en L0 tiene el WER más alto de los 20 audios (15.5 %, por una alucinación)
  y aun así detecta sus dos trampas y saca bien la promoción y el pago.
- **Correlación de Spearman** entre WER y acierto del registro: −0.35 en entrevistas (n = 5) y −0.25
  en llamadas (n = 20, `results/wer_vs_record_llamadas.csv`). Es débil y con estos n no se distingue
  de cero.

**Qué significa para quien reporta solo WER:** el WER cuenta todas las palabras por igual, pero el
registro depende de unas pocas (una cifra, una fecha, un nombre propio). Un 1 % de WER puede caer justo
en el salario, y un 9 % puede caer entero en muletillas. Además, parte de los errores del registro no
vienen del ASR sino del extractor (la resta de entrevista_02), y esos el WER no los ve nunca. Hay que
medir las dos capas por separado.

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

| Nivel | WER [IC 95 %] | CER | Trampas detectadas [IC 95 %] | Autocorrecciones | Totales erróneos | Direcciones |
|---|---|---|---|---|---|---|
| L0 | 7.5 % [4.5–11.8] | 4.6 % | 11/11 [74–100 %] | 3/3 | 3/3 | 5/5 |
| L1 | 6.2 % [5.3–7.4] | 3.5 % | 11/11 [74–100 %] | 3/3 | 3/3 | 5/5 |
| L2 | 6.3 % [4.9–7.7] | 2.9 % | 11/11 [74–100 %] | 3/3 | 3/3 | 5/5 |
| L3 | 10.4 % [8.1–12.7] | 5.0 % | 10/11 [62–98 %] | 3/3 | 3/3 | 4/5 |

Capa del registro (campos del pedido completo, no solo las trampas), con IC de Wilson
(`results/calls_ci.csv`):

| Nivel | Ítems correctos | Promoción | Forma de pago |
|---|---|---|---|
| L0 | 6/13 · 46 % [23–71] | 5/5 · 100 % [57–100] | 4/5 · 80 % [38–96] |
| L1 | 7/13 · 54 % [29–77] | 5/5 · 100 % [57–100] | 3/5 · 60 % [23–88] |
| L2 | 5/13 · 38 % [18–65] | 5/5 · 100 % [57–100] | 4/5 · 80 % [38–96] |
| L3 | 7/13 · 54 % [29–77] | 5/5 · 100 % [57–100] | 3/5 · 60 % [23–88] |

El WER de L3 sí se separa de L1 y L2 (los intervalos no se tocan), pero las curvas de campos no
muestran una tendencia: con 5 llamadas todos los intervalos de una misma columna se solapan. La capa
del registro está limitada por el extractor (modelo de 3B), no por el audio.

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

**Qué tan seguido acierta:** 4 de 5 llamadas bien clasificadas, 80 % [IC 95 % de Wilson: 38–96 %],
igual en los cuatro niveles. La rama «error del ASR» nunca se activó: en ninguna llamada el ASR
transcribió distinto el total entre niveles, así que esa mitad de la regla no quedó probada con datos
reales.

### Limitaciones

- Las direcciones de las llamadas usan nombres de calles reales de Lima con números inventados; no
  corresponden a ninguna persona.
- La parte final de llamada_03 no se grabó; su referencia refleja lo que sí se dijo (3:08 min).
- 5 audios por tarea: los promedios se mueven con un solo caso (ver la alucinación de llamada_01).
  Con n = 5 un 80 % de acierto por campo tiene un IC de 38–96 %: la muestra no permite decir qué
  campo es más difícil que otro, ni que la escalera degrade los campos del pedido. Sí permite decir
  que el LLM supera a las reglas (los intervalos del total no se solapan) y que medium int8 tiene
  menos WER que small en estas entrevistas.
- Las referencias se corrigieron con ayuda de dos modelos (ver «Referencias»), lo que favorece a esos
  modelos en el WER.
