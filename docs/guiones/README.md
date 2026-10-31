# Guiones de grabación

Diez guiones con contenido **inventado**: 5 entrevistas (Tarea 1) y 5 llamadas de venta de
restaurante (Tarea 2). Cada archivo trae arriba el registro esperado y cómo se dice cada dato en el
audio; esos mismos valores están en `data/ground_truth/*.json`.

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
| llamada_05 | — | — (cuadra: 106, llamada de control) | Av. La Marina 3175, dpto. 803 |
| **Total** | **3** | **3** | **5** |

Cada llamada dice todos los campos del registro: productos con **tamaño**, cantidad y precio
unitario, promoción, dirección, **forma de pago** (tarjeta, efectivo, Yape) y el total dicho en voz
alta (`total_dicho`). También trae distractores: precios de tamaños que no se piden, promociones
que no aplican, pisos, horas y minutos de entrega. El registro debe guardar el pedido final.

Cada guion (entrevistas y llamadas) tiene entre 365 y 415 palabras: unos 2:20 min hablando rápido
y unos 3 min leyendo con calma, dentro del rango de 2 a 4 minutos. Si una grabación sale por
debajo de 2 minutos, repítela más despacio, con pausas naturales.
`tests/test_guiones.py` comprueba el largo, las sumas y que precios, pago y direcciones aparezcan
en el texto.

## Entrevistas (Tarea 1)

La estructura sigue el laboratorio `LAB_Entrevistas.ipynb` de la sesión 10: primero se formalizan
los campos y sus valores permitidos, después el registro esperado de cada entrevista en JSON, y
recién entonces el texto. Como en ese laboratorio (el registro "despedido por fraude, pero apto
para recontratar"), una entrevista trae una inconsistencia a propósito.

| Campo | Tipo | Valores / formato | Se guarda |
|---|---|---|---|
| `anios_experiencia` | entero | años de trabajo profesional | el total, aunque se diga como suma o año de inicio |
| `ultimo_puesto` | texto | cargo tal como se dice | el último cargo formal, no la función ni el título de LinkedIn |
| `tecnologias` | lista | las de `config.yaml` | solo las que usó; no las que quiere aprender o dejó de usar |
| `pretension_salarial` | entero o null | soles mensuales | la cifra final; null si no la da |
| `disponibilidad` | fecha | AAAA-MM-DD | se dice relativa ("el lunes", "en un mes") y se guarda absoluta desde `fecha_entrevista` |
| `nivel_ingles` | categoría | básico / intermedio / avanzado / fluido | lo que dice que habla, aunque el CV diga otra cosa |

Ningún campo se dice limpio, y el orden cambia en cada entrevista:

| Entrevista | Orden en que salen los campos | Trampas principales |
|---|---|---|
| `entrevista_01` | tecnologías → puesto → inglés → salario → experiencia → disponibilidad | Excel que ya no usa; dos cargos; sueldo actual + rango; años por suma (5 + 1); "quince días de preaviso" |
| `entrevista_02` | salario → inglés → experiencia → puesto → tecnologías → disponibilidad | cuatro cifras de salario; años como "desde el dos mil dieciocho" (el 8 no se dice); Python que quiere aprender; "el lunes mismo" |
| `entrevista_03` | experiencia → disponibilidad → tecnologías → inglés → puesto → salario | dos autocorrecciones; **inconsistencia** CV "avanzado" vs. dice "básico"; rango y luego cifra |
| `entrevista_04` | puesto → salario → tecnologías → disponibilidad → inglés → experiencia | LinkedIn vs. contrato; "quince mil… no, quince mil quinientos"; "un mes" sin dígito; 13 vs. 12 años |
| `entrevista_05` | inglés → disponibilidad → experiencia → salario → tecnologías → puesto | "B uno"; años por suma (0,5 + 1,5); salario de prácticas que **no** es la expectativa → null |

`data/ground_truth/entrevistas.json` guarda, para cada entrevista, el registro esperado, la
`fecha_entrevista` y la `evidencia`: la frase literal de la que sale cada valor. Los años de la
`entrevista_02` y la `entrevista_05` no se dicen como número, así que un extractor que acierte
quedará igual `sin_verificar`: es el caso de "corregir en silencio" que pide analizar la tarea.

Sobre los guiones, el extractor por reglas acierta 8 de 30 campos. `tests/test_guiones.py`
comprueba que cada entrevista le haga fallar al menos dos, que el orden no se repita y que las
fechas de disponibilidad salgan de la evidencia.
