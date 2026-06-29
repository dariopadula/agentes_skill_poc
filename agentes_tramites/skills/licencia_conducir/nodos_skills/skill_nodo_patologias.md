# Nodo de Inferencia de Patologias y Restricciones Medicas

## Proposito

Este documento guia al LLM para interpretar descripciones ciudadanas sobre
condiciones de salud, restricciones medicas o medicacion permanente cuando la
persona no sabe si eso cuenta como "patologia" para el tramite de licencia de
conducir.

El objetivo del nodo no es armar una historia clinica ni reemplazar la pregunta
binaria del flujo. El objetivo es ayudar a decidir si una descripcion natural
debe tratarse administrativamente como `patologias = true`.

Ejemplos de entradas que si corresponden a este nodo:

- "Uso lentes, ¿eso cuenta?"
- "Soy hipertenso."
- "Tengo diabetes."
- "Tomo medicacion permanente."
- "Uso CPAP para dormir."
- "No se si lo mio cuenta como patologia."

## Casos que no deben entrar al LLM

Las respuestas binarias claras deben resolverse antes de llamar a este nodo:

- Si el usuario responde "si", "si tengo" o equivalente, el flujo local debe
  guardar `patologias = true`.
- Si el usuario responde "no", "no tengo", "ninguna" o equivalente, el flujo
  local debe guardar `patologias = false`.

Si el usuario ya sabe responder si o no, no hace falta inferir codigos ni pedir
detalle. Las dudas sobre requisitos o consecuencias de declarar patologias se
responderan despues, con el documento terminal correspondiente.

## Limites del nodo

- No diagnosticar enfermedades.
- No dar consejo medico.
- No indicar aptitud o ineptitud para conducir.
- No informar requisitos finales del tramite.
- No explicar consecuencias administrativas de una patologia.
- No decidir si el examen medico debe aprobarse o rechazarse.
- No seleccionar hojas terminales.
- No escribir directamente el campo `patologias`.
- No inventar codigos que no figuran en este documento.
- No asumir una condicion medica si el usuario no la menciono.

La inferencia debe ser confirmada por la persona antes de promoverse a
`patologias`.

## Campos de estado que puede proponer

Cuando el nodo detecta una posible condicion relevante, debe proponer estos
campos:

```json
{
  "patologias_inferidas": true,
  "codigos_patologias_inferidos": [2, 15],
  "condiciones_detectadas": [
    {
      "codigo": 2,
      "nombre": "Afecciones cardiovasculares",
      "texto_usuario": "soy hipertenso"
    },
    {
      "codigo": 15,
      "nombre": "Lentes de contacto",
      "texto_usuario": "uso lentes de contacto"
    }
  ],
  "patologias_inferencia_confianza": "alta",
  "patologias_inferencia_motivo": "El usuario menciono hipertension y lentes de contacto."
}
```

Los codigos son metadata auxiliar para trazabilidad y posibles mejoras futuras.
La seleccion de hoja terminal actual solo necesita promover `patologias = true`
o `patologias = false`.

Valores validos:

- `patologias_inferidas`: `true`, `false` o `null`.
- `codigos_patologias_inferidos`: lista de codigos numericos o lista vacia.
- `condiciones_detectadas`: lista de condiciones detectadas.
- `patologias_inferencia_confianza`: `alta`, `media`, `baja` o `null`.
- `patologias_inferencia_motivo`: explicacion breve, sin consejo medico.

## Contrato de salida

El LLM debe devolver siempre una decision estructurada con este formato:

```json
{
  "status": "detected",
  "patologias_inferidas": true,
  "codigos_patologias_inferidos": [3],
  "condiciones_detectadas": [
    {
      "codigo": 3,
      "nombre": "Diabetes",
      "texto_usuario": "tengo diabetes"
    }
  ],
  "confidence": "alta",
  "question": null,
  "reason": "El usuario menciono diabetes, que figura en la tabla con codigo 3."
}
```

Estados validos:

- `detected`: la descripcion corresponde a una posible patologia o restriccion
  administrativa relevante para el tramite.
- `not_detected`: la descripcion no coincide con las condiciones documentadas
  en esta guia.
- `need_input`: falta un dato concreto para clasificar la descripcion.
- `unknown`: no hay informacion suficiente para determinar si corresponde o no.

Reglas de salida:

- Si `status` es `detected`, `patologias_inferidas` debe ser `true`,
  `codigos_patologias_inferidos` debe contener al menos un codigo cuando haya
  coincidencia de tabla, y `condiciones_detectadas` debe describir cada
  coincidencia.
- Si `status` es `not_detected`, `patologias_inferidas` debe ser `false`,
  `codigos_patologias_inferidos` debe ser una lista vacia y `question` debe ser
  `null`.
- Si `status` es `need_input`, no inferir patologias; `question` debe contener
  una pregunta concreta.
- Si `status` es `unknown`, no inferir patologias; `question` puede pedir al
  usuario que responda si tiene una enfermedad cronica, restriccion medica o
  medicacion permanente.

## Confirmacion posterior

Este nodo no confirma por si mismo. El flujo conversacional debe usar la
decision `detected` para preguntar algo como:

```text
Entendi que lo que mencionaste puede considerarse una patologia o restriccion
relevante para el tramite. ¿Es correcto?
```

Solo si la persona confirma, el sistema puede promover:

```json
{
  "patologias": true,
  "codigos_patologias": [3]
}
```

Si el nodo devuelve `not_detected`, el flujo debe explicar que esa descripcion
no esta en la guia cargada y que no se registrara como patologia con esa
informacion. Luego puede preguntar si la persona tiene otra condicion que quiera
mencionar:

```text
No encontre eso dentro de la guia de patologias o restricciones medicas que
tengo cargada para este tramite. Con esa informacion no lo voy a registrar como
patologia. ¿Tenes alguna otra condicion cronica, restriccion medica o medicacion
permanente que quieras mencionar?
```

Si la persona rechaza una inferencia, el sistema debe limpiar los campos
inferidos y pedir una aclaracion o una respuesta binaria.

## Tabla de mapeo linguistico

| Terminos comunes del usuario | Condicion administrativa | Codigo |
| :--- | :--- | :---: |
| "uso lentes", "no veo bien", "cataratas", "operado de la vista", "miopia" | Afecciones oculares | 1 |
| "presion alta", "hipertenso", "problemas de corazon", "arritmia" | Afecciones cardiovasculares | 2 |
| "diabetes", "azucar en sangre", "insulina", "pastillas para la glucosa" | Diabetes | 3 |
| "sordo", "uso audifono", "me cuesta escuchar" | Afecciones auditivas | 5 |
| "ataques", "epilepsia", "convulsiones" | Epilepsia | 7 |
| "artritis", "protesis", "problemas de cadera", "movilidad reducida" | Trastornos osteo-musculo-articulares | 8 |
| "depresion", "ansiedad", "tomo medicacion psiquiatrica", "psicologo", "psiquiatra" | Psiquiatria | 10 |
| "colesterol alto", "trigliceridos", "dislipemia" | Dislipemias | 11 |
| "uso lentes de contacto", "lentillas" | Lentes de contacto | 15 |
| "me cuesta ver de noche", "encandilamiento", "ceguera nocturna" | Vision nocturna limite | 24 |
| "glaucoma", "presion en el ojo" | Glaucoma | 33 |
| "solo puedo manejar de dia" | Conduccion solo con luz solar | 31 |
| "coche adaptado", "coche para discapacitado", "embrague al volante" | Coche adaptado | 37 |
| "apnea", "ronco mucho", "uso maquina para dormir", "CPAP" | Trastornos del sueno | 42 |

## Reglas de interpretacion

### Respuestas binarias

Si llega al nodo una respuesta binaria clara por error, no intentar enriquecerla
con codigos:

- "si" o equivalente: devolver `detected` solo si el contrato tecnico lo exige,
  pero sin codigos; el flujo local deberia haber resuelto `patologias = true`.
- "no" o equivalente: devolver `not_detected`; el flujo local deberia haber
  resuelto `patologias = false`.

La implementacion del grafo debe evitar llamar al LLM en estos casos.

### Medicacion permanente

Si el usuario menciona medicacion permanente pero no indica para que condicion
la toma, devolver `need_input` y preguntar:

```text
¿La medicacion permanente es por presion, diabetes, salud mental, colesterol u otra condicion?
```

No inferir un codigo solo por la palabra "medicacion".

### Varias condiciones

Si el usuario menciona varias condiciones, devolver todos los codigos que
correspondan segun la tabla.

Ejemplo:

- "soy hipertenso y uso lentes de contacto" -> codigos `[2, 15]`.

### Condiciones especiales para etapas posteriores

Si se detecta alguno de estos codigos, conservarlo igual que los demas y
mencionarlo solo en el motivo interno:

- `24`: vision nocturna limite.
- `31`: conduccion solo con luz solar.
- `37`: coche adaptado.

Este nodo no debe explicar consecuencias administrativas. Esa informacion debe
salir de documentos terminales o de otra etapa controlada del flujo.

## Ejemplos de salida

### Caso detectado

Usuario:

```text
Tengo diabetes.
```

Salida:

```json
{
  "status": "detected",
  "patologias_inferidas": true,
  "codigos_patologias_inferidos": [3],
  "condiciones_detectadas": [
    {
      "codigo": 3,
      "nombre": "Diabetes",
      "texto_usuario": "tengo diabetes"
    }
  ],
  "confidence": "alta",
  "question": null,
  "reason": "El usuario menciono diabetes, que corresponde al codigo 3."
}
```

### Varias condiciones

Usuario:

```text
Soy hipertenso y uso lentes de contacto.
```

Salida:

```json
{
  "status": "detected",
  "patologias_inferidas": true,
  "codigos_patologias_inferidos": [2, 15],
  "condiciones_detectadas": [
    {
      "codigo": 2,
      "nombre": "Afecciones cardiovasculares",
      "texto_usuario": "soy hipertenso"
    },
    {
      "codigo": 15,
      "nombre": "Lentes de contacto",
      "texto_usuario": "uso lentes de contacto"
    }
  ],
  "confidence": "alta",
  "question": null,
  "reason": "El usuario menciono hipertension y lentes de contacto."
}
```

### No detectado

Usuario:

```text
Me resfrie la semana pasada.
```

Salida:

```json
{
  "status": "not_detected",
  "patologias_inferidas": false,
  "codigos_patologias_inferidos": [],
  "condiciones_detectadas": [],
  "confidence": "media",
  "question": null,
  "reason": "La descripcion no coincide con las condiciones documentadas en la guia."
}
```

### Necesita aclaracion

Usuario:

```text
Tomo medicacion permanente.
```

Salida:

```json
{
  "status": "need_input",
  "patologias_inferidas": null,
  "codigos_patologias_inferidos": [],
  "condiciones_detectadas": [],
  "confidence": "media",
  "question": "¿La medicacion permanente es por presion, diabetes, salud mental, colesterol u otra condicion?",
  "reason": "El usuario menciono medicacion permanente, pero no indico la condicion asociada."
}
```

### Caso desconocido

Usuario:

```text
No se si lo mio cuenta.
```

Salida:

```json
{
  "status": "unknown",
  "patologias_inferidas": null,
  "codigos_patologias_inferidos": [],
  "condiciones_detectadas": [],
  "confidence": null,
  "question": "Contame brevemente cual es la condicion, restriccion medica o medicacion permanente.",
  "reason": "El usuario no describio una condicion que permita clasificar."
}
```

## Fuentes de referencia

- `skills/licencia_conducir/material_util/codigosdepatologiasab24_8.pdf`
- `skills/licencia_conducir/material_util/patologias_aux.md`
- Protocolo Agendas y Multas 2019: codigos de patologias.
- Digesto Departamental: parametros medicos y causales relacionadas.
