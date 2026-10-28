# Guiones de grabación

Diez guiones con contenido **inventado**: 5 entrevistas (Tarea 1) y 5 llamadas de venta de
restaurante (Tarea 2). Cada archivo trae arriba los datos que deben quedar claros en el audio, y
esos mismos valores están en `data/ground_truth/*.json`.

## Cómo grabar

- Graba en un lugar callado, con el celular a unos 20–30 cm de la boca. El ruido se agrega después (nivel L3).
- Haz los dos papeles tú, o grábalo con alguien de confianza que dé su consentimiento por escrito.
- Lee con naturalidad. Puedes adaptar el género de palabras como "desarrollador" o "atento",
  pero **si cambias un dato** (un número, un puesto, una tecnología), cámbialo también aquí y en el ground truth.
- Nombra cada audio igual que su guion: `entrevista_01.m4a`, `llamada_03.m4a`, etc.
- Copia los audios a `data/audio/entrevistas/` y `data/audio/llamadas/` y guarda una copia en Drive.

## Si te sales del guion

La referencia para el WER es lo que **realmente dijiste**. Si improvisas o te equivocas, corrige la
línea en el guion y vuelve a generar las referencias:

```bash
python scripts/make_references.py
```

El script toma solo las líneas que empiezan con `**ROL:**` y escribe `data/references/<id>.txt`.

## Trampas de la Tarea 2

| Llamada | Autocorrección | Total erróneo | Dígitos |
|---|---|---|---|
| llamada_01 | pizzas 2 → 3 | dice 155, correcto 141 | Av. Arequipa 1234 |
| llamada_02 | gaseosas 1 → 2 | — (cuadra: 100) | Jr. Junín 456, dpto. 302 |
| llamada_03 | — | dice 94, correcto 84 | Calle Los Pinos 789 |
| llamada_04 | hamburguesas 4 → 5 | dice 135, correcto 125 | Av. Brasil 2050, int. 4 |
| llamada_05 | — | — (cuadra: 106, llamada de control) | Av. La Marina 3175 |
| **Total** | **3** | **3** | **5** |

## Casos difíciles a propósito (Tarea 1)

- `entrevista_02`: menciona el sueldo actual (7000) además de la expectativa (9000).
- `entrevista_03`: se corrige los años de experiencia ("cuatro, perdón, tres").
- `entrevista_04`: dice "llevo doce años" en vez de "años de experiencia", y la disponibilidad es "en un mes", que el extractor por reglas no detecta.
- `entrevista_05`: no da expectativa salarial, así que el valor correcto es `null`.
