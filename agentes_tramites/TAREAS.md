# TAREAS

Registro de mejoras, cambios y agregados pendientes del proyecto.

Este archivo sirve para ordenar el trabajo antes de modificar el codigo. Cada
tarea debe describir la necesidad, el objetivo, un plan de solucion y su estado.

La carpeta `versiones/` mantiene el registro de cambios ya implementados. Este
archivo mantiene el registro de tareas propuestas, aprobadas, en curso o
cerradas.

## Estados

- Pendiente
- En analisis
- Aprobada
- En progreso
- Hecha
- Bloqueada
- Descartada

## Criterios de uso

- Crear una tarea por cada mejora, cambio o agregado relevante.
- Mantener el plan breve y concreto.
- No marcar una tarea como `En progreso` hasta que haya aprobacion explicita.
- Al cerrar una tarea, completar la seccion `Resultado`.
- Si la tarea implica cambios en codigo, tambien debe registrarse luego en
  `versiones/`.

## Plantilla

```md
## T-000 - Nombre breve de la tarea

**Estado:** Pendiente
**Prioridad:** Alta / Media / Baja
**Fecha de creacion:** YYYY-MM-DD
**Area:** Orquestador / Skill licencia / Tests / Documentacion / Arquitectura / Otro

### Problema o necesidad

Descripcion clara de que se quiere mejorar, cambiar o agregar.

### Objetivo

Resultado concreto esperado.

### Plan propuesto

1. Paso uno.
2. Paso dos.
3. Paso tres.

### Archivos posiblemente afectados

- `archivo.py`
- `skills/...`

### Riesgos o dudas

- Riesgo o duda pendiente.

### Resultado

Pendiente de ejecucion.
```

---

## Tareas activas

## T-001 - Confirmacion e incertidumbre en el orquestador

**Estado:** Hecha
**Prioridad:** Alta
**Fecha de creacion:** 2026-06-26
**Area:** Orquestador / Router / Skill licencia / Arquitectura

### Problema o necesidad

Hoy el orquestador identifica automaticamente una skill a partir de la consulta
del usuario. Esto puede funcionar con pocas skills, pero cuando existan muchos
tramites registrados puede haber consultas ambiguas.

Por ejemplo, `quiero sacar la libreta` podria referirse a licencia de conducir,
pero en el futuro tambien podria coincidir con otros tramites o documentos.
En cambio, `quiero sacar la libreta de conducir` parece una consulta mucho mas
clara.

Tambien existe un riesgo en la extraccion temprana de parametros dentro de la
skill de licencia de conducir. Por ejemplo, `quiero sacar la licencia de
conducir` podria interpretarse como `tramite = primera_vez`, pero esa decision
no siempre es segura. El usuario podria querer renovar, consultar requisitos,
pedir un duplicado, sacar turno o simplemente hacer una consulta general.

El riesgo mas importante es llegar a una hoja terminal incorrecta y entregar
requisitos concretos para un caso mal interpretado. Antes de mostrar la
respuesta final del nodo terminal, puede ser conveniente presentar un resumen
breve del caso entendido y pedir confirmacion al usuario.

### Objetivo

Disenar un mecanismo para manejar incertidumbre sin volver al orquestador
molesto o excesivamente preguntador.

El sistema deberia poder:

- Confirmar el tramite detectado cuando la consulta sea ambigua.
- Evitar tomar inferencias debiles como datos firmes.
- Distinguir entre datos explicitamente dichos por el usuario y datos inferidos.
- Mostrar al usuario, de forma clara, que interpreto el sistema y que datos esta
  usando como entrada.
- Confirmar el caso armado antes de entregar informacion de una hoja terminal,
  por ejemplo tramite, categoria, edad y patologias cuando esos datos afecten la
  seleccion del documento final.

### Plan propuesto

1. Revisar el contrato actual entre router, orquestador, estado y handlers de
   skills.
2. Definir criterios de confianza para decidir cuando una skill puede activarse
   directamente y cuando requiere confirmacion.
3. Proponer una estructura para representar campos confirmados, campos
   inferidos y campos pendientes de confirmacion.
4. Revisar la extraccion actual de parametros de licencia de conducir para
   evitar que frases ambiguas como `sacar la licencia` se conviertan
   automaticamente en `primera_vez`.
5. Disenar una confirmacion resumida del caso antes de cargar el documento
   terminal de licencia de conducir.
6. Definir como mostrar al usuario las decisiones relevantes del sistema sin
   exponer detalles tecnicos innecesarios.
7. Agregar pruebas para los casos ambiguos, los casos claramente identificados y
   la confirmacion previa al nodo terminal.

### Archivos posiblemente afectados

- `orchestrator.py`
- `routers.py`
- `state.py`
- `skills/licencia_conducir/matcher.py`
- `skills/licencia_conducir/graph.py`
- `tests/...`

### Riesgos o dudas

- Si se confirma demasiado, la conversacion puede volverse lenta o molesta.
- Si se confirma muy poco, el sistema puede avanzar con interpretaciones
  incorrectas.
- Hay que definir si la confirmacion pertenece al orquestador, al router, a la
  skill o a una combinacion de esas capas.
- La confirmacion del caso previo al nodo terminal probablemente pertenezca a la
  skill, porque cada tramite conoce que datos afectan su seleccion final.
- Hay que cuidar que la solucion escale a muchas skills sin agregar logica
  rigida basada en grandes bloques condicionales.

### Resultado

Implementada el 2026-06-26.

Se agrego confirmacion de skill ambigua en el orquestador, se hizo mas prudente
la extraccion de `primera_vez` en licencia de conducir y se incorporo una
confirmacion resumida del caso antes de cargar la hoja terminal.

Prueba ejecutada:

```powershell
..\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Resultado: 35 tests OK.

## T-002 - Interpretacion guiada y autocontenida en licencia de conducir

**Estado:** Pendiente
**Prioridad:** Alta
**Fecha de creacion:** 2026-06-26
**Area:** Skill licencia / Documentacion / LLM / Arquitectura

### Problema o necesidad

La skill de licencia de conducir hoy puede pedir datos que la ciudadania no
necesariamente conoce de antemano. Por ejemplo, una persona puede no saber que
categoria administrativa corresponde a su caso (`A`, `G1`, `G2`, `B`, etc.), o
puede no saber si una condicion medica que tiene cuenta como patologia o
restriccion relevante para el tramite.

Preguntar directamente por codigos o respuestas binarias puede convertir al
agente en un formulario rigido. La persona deberia poder responder en lenguaje
natural, por ejemplo:

- `quiero manejar autos comunes`
- `quiero manejar una moto chica`
- `quiero manejar camiones`
- `tengo diabetes`
- `soy hipertenso`
- `uso lentes`

El sistema deberia ayudar a interpretar esas respuestas dentro del marco de la
skill, sin obligar al usuario a consultar informacion fuera de la aplicacion.

### Objetivo

Disenar una interpretacion guiada, precisa y autocontenida para los pasos de la
skill de licencia que lo ameriten, especialmente categoria de licencia y
patologias/restricciones medicas.

El sistema deberia poder:

- Usar documentos o taxonomias propias de la skill como marco de referencia.
- Interpretar respuestas ciudadanas en lenguaje natural cuando sea seguro.
- Explicar opciones disponibles cuando no pueda inferir una respuesta.
- Evitar inventar categorias, patologias o equivalencias no documentadas.
- Devolver dudas o pedidos de aclaracion cuando la respuesta sea ambigua.
- Mantener el camino conversacional claro, guiado y autocontenido dentro de la
  aplicacion.

### Plan propuesto

1. Identificar que preguntas de licencia requieren interpretacion guiada, con
   foco inicial en `categoria` y `patologias`.
2. Crear o consolidar documentos/taxonomias internas de la skill para categorias
   de licencia y patologias/restricciones relevantes.
3. Definir un contrato estructurado para interpretar respuestas naturales, por
   ejemplo campo detectado, valor sugerido, confianza, explicacion y necesidad
   de aclaracion.
4. Evaluar un nodo o componente LLM dentro de la skill que use exclusivamente
   esos documentos/taxonomias como contexto.
5. Definir fallback local o respuesta explicativa cuando el LLM no este
   disponible.
6. Integrar la interpretacion con el flujo de recoleccion de datos sin saltar la
   confirmacion final del caso definida en `T-001`.
7. Agregar pruebas para respuestas naturales, casos ambiguos y casos no
   documentados.

### Archivos posiblemente afectados

- `skills/licencia_conducir/graph.py`
- `skills/licencia_conducir/matcher.py`
- `skills/licencia_conducir/document_qa.py`
- `skills/licencia_conducir/hojas_terminales.json`
- `skills/licencia_conducir/documentos_terminales/...`
- `tests/...`

### Riesgos o dudas

- El LLM no debe inventar equivalencias entre lenguaje ciudadano y categorias
  administrativas.
- La interpretacion de patologias debe evitar diagnosticos medicos; solo debe
  clasificar contra informacion documentada por la skill.
- Si la documentacion interna es incompleta, el sistema debe pedir aclaracion o
  explicar que no puede determinarlo.
- Hay que decidir si las taxonomias viven en JSON, Markdown u otro formato
  simple y mantenible.
- Esta tarea depende parcialmente de `T-001`, porque la interpretacion guiada no
  debe eliminar la confirmacion final del caso antes del nodo terminal.

### Resultado

Pendiente de analisis e implementacion.

## T-003 - Router escalable por recuperacion de skills candidatas

**Estado:** Pendiente
**Prioridad:** Alta
**Fecha de creacion:** 2026-06-26
**Area:** Orquestador / Router / Embeddings / Arquitectura

### Problema o necesidad

Hoy el router decide la skill usando el catalogo completo cargado desde
`skills/skill_registry.json`. Con pocas skills esto es razonable, pero si el
proyecto crece a decenas o cientos de tramites, evaluar todo el catalogo en cada
consulta puede volverse pesado, caro y menos preciso.

En particular, cuando se usa un router LLM, enviar todo el catalogo completo al
modelo no escala bien. Tambien puede aumentar el riesgo de decisiones ambiguas o
de comparaciones innecesarias entre skills poco relacionadas.

### Objetivo

Disenar una etapa inicial de recuperacion de skills candidatas para que el
orquestador trabaje sobre un subconjunto reducido y relevante antes de decidir o
pedir confirmacion.

El sistema deberia poder:

- Construir una representacion semantica de cada skill a partir de su metadata.
- Recuperar las `top_k` skills mas parecidas a la consulta del usuario.
- Pasar solo esas candidatas a la etapa de decision final.
- Funcionar sin introducir bases vectoriales externas en la POC.
- Mantener fallback simple si los embeddings no estan disponibles.

### Plan propuesto

1. Definir el texto de indexacion de cada skill usando nombre, descripcion,
   ejemplos de usuario, cuando usar y palabras clave.
2. Evaluar un indice local simple de embeddings para skills, por ejemplo un
   archivo JSONL versionable o regenerable.
3. Implementar recuperacion en memoria por similitud coseno para obtener las
   skills candidatas.
4. Definir parametros iniciales como `top_k` y umbral minimo de similitud.
5. Integrar la recuperacion como primera etapa del router, sin reemplazar la
   decision final.
6. Hacer que la decision final use solo el catalogo reducido de candidatas,
   mediante router local, LLM o confirmacion segun corresponda.
7. Agregar pruebas para consultas claras, ambiguas, sin coincidencias y casos
   donde la skill correcta debe quedar dentro de las candidatas.

### Archivos posiblemente afectados

- `orchestrator.py`
- `routers.py`
- `skill_registry.py`
- `skills/skill_registry.json`
- `llm_client.py`
- `tests/...`
- `skills/...`

### Riesgos o dudas

- Un umbral demasiado alto puede dejar afuera la skill correcta.
- Un umbral demasiado bajo puede no reducir lo suficiente el catalogo.
- La calidad de recuperacion depende mucho del texto de indexacion de cada
  skill.
- Hay que decidir si el indice se genera manualmente, por script o al iniciar la
  aplicacion.
- No conviene introducir por ahora bases vectoriales externas ni frameworks
  pesados.
- Debe existir fallback cuando no haya embeddings configurados o el indice no
  este disponible.

### Resultado

Pendiente de analisis e implementacion.
