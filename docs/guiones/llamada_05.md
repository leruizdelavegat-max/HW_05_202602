# llamada_05 (control)

Pizzería La Plaza (inventada) · Duración estimada: 2:40 min

Llamada sin errores: sirve para comprobar que el sistema **no** marca problemas donde no los hay.

## Registro esperado

```json
{
  "items": [
    {"producto": "pizza americana", "tamano": "mediana", "cantidad": 2, "precio_unitario": 38},
    {"producto": "pan al ajo", "tamano": null, "cantidad": 1, "precio_unitario": 12},
    {"producto": "chicha morada", "tamano": "jarra de un litro", "cantidad": 1, "precio_unitario": 18}
  ],
  "promocion": null,
  "direccion_o_contrato": "Avenida La Marina 3175, torre B, departamento 803, San Miguel",
  "metodo_pago": "efectivo",
  "total_dicho": 106
}
```

Total correcto: 2 × 38 + 12 + 18 = **106** (cuadra).

## Trampas

| Tipo | Qué pasa en el audio |
|---|---|
| Dígitos | Avenida La Marina 3175, departamento 803 |
| Distractores | Borde de queso que **no** pide (6), precio de las alitas (24), "seis unidades", pregunta por un descuento que no existe |

---

**VENDEDOR:** Pizzería La Plaza, buenas noches. ¿Es delivery o recojo en tienda?

**CLIENTE:** Delivery, por favor. ¿La pizza americana lleva solo jamón y queso?

**VENDEDOR:** Jamón, queso mozzarella y orégano. Es la más pedida.

**CLIENTE:** ¿Y qué otras pizzas tienen?

**VENDEDOR:** Hawaiana, pepperoni, vegetariana y la de la casa, que lleva tocino y champiñones.

**CLIENTE:** En mi casa solo comen la americana, así que vamos con esa. Entonces quiero dos pizzas americanas medianas.

**VENDEDOR:** Dos americanas medianas, a treinta y ocho soles cada una. ¿Masa delgada o tradicional?

**CLIENTE:** Tradicional.

**VENDEDOR:** ¿Le agregamos borde de queso? Cuesta seis soles más por pizza.

**CLIENTE:** No, así está bien, gracias.

**VENDEDOR:** Perfecto. ¿Algo para acompañar?

**CLIENTE:** ¿Qué entradas tienen?

**VENDEDOR:** Pan al ajo, alitas y palitos de queso. El pan al ajo está a doce soles y trae seis unidades; las alitas, a veinticuatro.

**CLIENTE:** Un pan al ajo.

**VENDEDOR:** Un pan al ajo, doce soles. ¿Y de beber?

**CLIENTE:** ¿Tienen chicha morada?

**VENDEDOR:** Sí, en jarra de un litro, a dieciocho soles.

**CLIENTE:** Una jarra de chicha morada, entonces.

**VENDEDOR:** ¿La quiere con el hielo aparte?

**CLIENTE:** Sí, aparte, por favor, porque si no se diluye.

**VENDEDOR:** Le repito el pedido: dos pizzas americanas medianas, setenta y seis soles; un pan al ajo, doce; y una jarra de chicha morada, dieciocho. El total es ciento seis soles.

**CLIENTE:** ¿Hay algún descuento por pagar en efectivo?

**VENDEDOR:** Por ahora no tenemos promociones, disculpe.

**CLIENTE:** Está bien. Pago en efectivo, con sencillo justo.

**VENDEDOR:** Perfecto. ¿Cuál es la dirección?

**CLIENTE:** Avenida La Marina tres mil ciento setenta y cinco, en San Miguel. Es un condominio; el departamento es el ochocientos tres de la torre B.

**VENDEDOR:** Avenida La Marina tres mil ciento setenta y cinco, San Miguel, torre B, departamento ochocientos tres. ¿El repartidor puede subir?

**CLIENTE:** No, tiene que dejarlo en recepción. Yo bajo a recogerlo.

**VENDEDOR:** Entonces le digo que pregunte por el departamento ochocientos tres, para que lo llamen desde recepción.

**CLIENTE:** Sí, así está bien.

**VENDEDOR:** Muy bien. Llega en unos cuarenta minutos.

**CLIENTE:** ¿Y si se demora más de una hora?

**VENDEDOR:** Le llamamos para avisarle, pero normalmente llega antes. ¿Le mandamos ají y salsa de ajo?

**CLIENTE:** Sí, dos sobres de cada uno, por favor.

**CLIENTE:** Gracias. ¿Pueden asegurarse de que llegue caliente?

**VENDEDOR:** Siempre sale del horno directo a la caja térmica. Buenas noches.

**CLIENTE:** Buenas noches, gracias.
