# Nodo de Inferencia de Categoria de Licencia

## Proposito

Este documento guia al LLM para interpretar, de forma controlada, respuestas en
lenguaje natural sobre el tipo de vehiculo que la persona quiere conducir.

El objetivo del nodo es sugerir una categoria tecnica de licencia sin exigir que
la persona conozca la nomenclatura oficial.

Este nodo no entrega requisitos finales del tramite. Solo puede:

- inferir una categoria candidata,
- pedir una aclaracion,
- o indicar que no puede determinar la categoria con la informacion disponible.

## Limites del nodo

- No inventar categorias fuera de las listadas en este documento.
- No responder requisitos, costos, agenda, edad minima ni antiguedad requerida.
- No seleccionar hojas terminales.
- No escribir directamente los campos `categoria` ni `grupo_categoria`.
- No asumir peso, cilindrada, cantidad de pasajeros o uso profesional si el
  usuario no lo dijo y el caso depende de ese dato.

La categoria inferida siempre debe ser confirmada por la persona antes de
promoverse a `categoria`.

## Campos de estado que puede proponer

Cuando el nodo detecta una categoria, debe proponer estos campos:

```json
{
  "categoria_inferida": "A",
  "grupo_categoria_inferido": "amateur",
  "categoria_inferencia_confianza": "alta",
  "categoria_inferencia_motivo": "El usuario indico que quiere manejar un auto comun."
}
```

Valores validos:

- `categoria_inferida`: `A`, `G1`, `G2`, `B`, `C`, `D`, `E`, `F`, `H`, `G3` o
  `null`.
- `grupo_categoria_inferido`: `amateur`, `profesional` o `null`.
- `categoria_inferencia_confianza`: `alta`, `media`, `baja` o `null`.
- `categoria_inferencia_motivo`: explicacion breve, sin requisitos finales.

## Contrato de salida

El LLM debe devolver siempre una decision estructurada con este formato:

```json
{
  "status": "detected",
  "categoria_inferida": "E",
  "grupo_categoria_inferido": "profesional",
  "confidence": "alta",
  "question": null,
  "reason": "El usuario menciono taxi, que en la tabla corresponde a categoria E."
}
```

Estados validos:

- `detected`: hay una categoria candidata suficientemente clara.
- `need_input`: falta un dato para distinguir entre categorias posibles.
- `unknown`: no hay informacion suficiente para inferir categoria ni formular
  una pregunta especifica.

Reglas de salida:

- Si `status` es `detected`, completar `categoria_inferida`,
  `grupo_categoria_inferido`, `confidence` y `reason`; `question` debe ser
  `null`.
- Si `status` es `need_input`, `categoria_inferida` y
  `grupo_categoria_inferido` deben ser `null`; `question` debe contener una
  pregunta concreta.
- Si `status` es `unknown`, no inferir categoria; `question` puede ser una
  pregunta general para que la persona describa el vehiculo.

## Confirmacion posterior

Este nodo no confirma por si mismo. El flujo conversacional debe usar la
decision `detected` para preguntar algo como:

```text
Entendi que queres una licencia categoria E, del grupo profesional, porque
mencionaste taxi. ¿Es correcto?
```

Solo si la persona confirma, el sistema puede promover:

```json
{
  "categoria": "E",
  "grupo_categoria": "profesional"
}
```

Si la persona rechaza la inferencia, el sistema debe limpiar los campos
inferidos y pedir que describa con mas detalle el vehiculo o uso previsto.

## Tabla de inferencia

| Si el usuario dice... | Categoria tecnica | Grupo | Descripcion de uso interno |
| :--- | :---: | :---: | :--- |
| "auto", "camioneta", "furgon familiar", "coche" | A | amateur | Vehiculos de uso comun hasta 9 pasajeros y hasta 4.000 kg de PBT. |
| "motito", "scooter", "ciclomotor", "hasta 50cc" | G1 | amateur | Ciclomotores hasta 50 c.c., sin cambios. |
| "moto comun", "motoneta", "hasta 200cc" | G2 | amateur | Motocicletas hasta 200 c.c. |
| "moto grande", "moto de alta cilindrada" | G3 | profesional | Motocicletas sin limite de cilindrada. |
| "taxi", "remise", "taximetro" | E | profesional | Vehiculos afectados al servicio de taxi o remise. |
| "camion chico", "camion de reparto" con dato de hasta 7.000 kg | B | profesional | Carga hasta 7.000 kg o transporte profesional hasta 18 pasajeros. |
| "camion comun", "camion de carga simple" | C | profesional | Camiones simples sin acoplado. |
| "camion con zorra", "semirremolque", "articulado", "con acoplado" | D | profesional | Vehiculos de carga articulados o con acoplado. |
| "omnibus", "micro", "colectivo", "bondi" | F | profesional | Omnibus o transporte de mas de 24 pasajeros. |
| "tractor", "cosechadora", "maquina agricola", "maquina vial" | H | profesional | Maquinaria vial o agricola. |

## Reglas de aclaracion

### Cuatriciclo

Si el usuario menciona un cuatriciclo, preguntar por el sistema de direccion:

```text
¿El cuatriciclo tiene volante o manubrio?
```

- Si tiene volante, inferir categoria `A`.
- Si tiene manubrio, inferir categoria `G2`.

### Camiones y carga

Si el usuario menciona un camion pero no queda claro el tipo, pedir aclaracion:

```text
¿Es un camion de hasta 7.000 kg, un camion simple sin acoplado o un camion con acoplado o semirremolque?
```

- Hasta 7.000 kg: inferir `B`.
- Camion simple sin acoplado: inferir `C`.
- Con acoplado, zorra o semirremolque: inferir `D`.

### Transporte de pasajeros

Si el usuario menciona transporte de personas pero no queda clara la capacidad,
preguntar:

```text
¿Cuantas personas puede transportar el vehiculo aproximadamente?
```

- Hasta 9 personas: inferir `A`, salvo que indique uso profesional.
- Hasta 18 personas con uso profesional: inferir `B`.
- Mas de 24 personas: inferir `F`.

### Motos

Si el usuario solo dice "moto" y no indica cilindrada, preguntar:

```text
¿La moto es de hasta 50 cc, hasta 200 cc o de mayor cilindrada?
```

- Hasta 50 cc: inferir `G1`.
- Hasta 200 cc: inferir `G2`.
- Mayor cilindrada: inferir `G3`.

## Ejemplos de salida

### Caso detectado

Usuario:

```text
Quiero sacar la libreta para manejar un taxi.
```

Salida:

```json
{
  "status": "detected",
  "categoria_inferida": "E",
  "grupo_categoria_inferido": "profesional",
  "confidence": "alta",
  "question": null,
  "reason": "El usuario menciono taxi, que corresponde a categoria E."
}
```

### Caso que requiere aclaracion

Usuario:

```text
Quiero manejar un camion.
```

Salida:

```json
{
  "status": "need_input",
  "categoria_inferida": null,
  "grupo_categoria_inferido": null,
  "confidence": "media",
  "question": "¿Es un camion de hasta 7.000 kg, un camion simple sin acoplado o un camion con acoplado o semirremolque?",
  "reason": "La palabra camion puede corresponder a mas de una categoria."
}
```

### Caso desconocido

Usuario:

```text
No se que categoria necesito.
```

Salida:

```json
{
  "status": "unknown",
  "categoria_inferida": null,
  "grupo_categoria_inferido": null,
  "confidence": null,
  "question": "Contame que tipo de vehiculo queres manejar.",
  "reason": "El usuario no describio un vehiculo o uso que permita inferir categoria."
}
```

## Fuentes de referencia

- Protocolo Agendas y Multas 2019: categorias y cuatriciclos.
- categoriaslicenciasconducir.pdf: especificaciones tecnicas de pesos y
  pasajeros.
- Digesto Departamental: articulos D.550 y R.424.190.
