# Skill de Identificación de Salud (Capa de Extracción Conversacional)

## Propósito
Este documento sirve como guía de instrucciones para que el LLM analice la respuesta del ciudadano a la pregunta: **"¿Padece alguna enfermedad crónica o toma medicación permanente?"**. Su función es actuar como un "traductor" entre el lenguaje natural del usuario y los códigos administrativos del Digesto Departamental de Montevideo, almacenando la información sin interrumpir el flujo de preguntas iniciales.

## Instrucciones para el LLM (Agente de Extracción)
1. **Detección Activa:** Identificar menciones a síntomas, nombres de enfermedades o tipos de medicación en el mensaje del usuario [1, 2].
2. **Variable de Control:** Si se detecta cualquier condición de salud, establecer la variable de estado `tiene_patologias` en `true`.
3. **Mapeo de Códigos:** Cruzar los términos del usuario con la "Tabla de Mapeo Lingüístico" (abajo) para obtener el código numérico correspondiente [3, 4].
4. **Persistencia (Vector de Salud):** Guardar los códigos detectados en una lista o vector llamado `vector_patologias`.
5. **No Interrupción:** No explicar requisitos médicos ni restricciones en este paso. El agente debe limitarse a confirmar la recepción (ej: "Entendido, tomo nota") y proceder a la siguiente pregunta del grafo (ej: Edad o Categoría) [5].

## Tabla de Mapeo Lingüístico (Ciudadano -> Código IM)

| Términos Comunes del Usuario | Patología Identificada | Código Oficial |
| :--- | :--- | :---: |
| "Uso lentes", "no veo bien", "cataratas", "operado de la vista", "miopía" | Afecciones Oculares | **1** |
| "Presión alta", "hipertenso", "problemas de corazón", "arritmia" | Afecciones Cardiovasculares | **2** |
| "Diabetes", "azúcar en sangre", "insulina", "pastillas para la glucosa" | Diabetes | **3** |
| "Sordo", "uso audífono", "me cuesta escuchar" | Afecciones Auditivas | **5** |
| "Ataques", "epilepsia", "convulsiones" | Epilepsia | **7** |
| "Artritis", "prótesis", "problemas de cadera", "movilidad reducida" | Trastornos Osteo-musculo-articular | **8** |
| "Depresión", "ansiedad", "tomo medicación psiquiátrica", "psicólogo" | Psiquiatría | **10** |
| "Colesterol alto", "triglicéridos", "dislipemia" | Dislipemias | **11** |
| "Uso lentes de contacto", "lentillas" | Lentes de contacto | **15** |
| "Me cuesta ver de noche", "encandilamiento", "ceguera nocturna" | **Visión nocturna límite** | **24** |
| "Glaucoma", "presión en el ojo" | Glaucoma | **33** |
| "Solo puedo manejar de día" | **Conducción solo luz solar** | **31** |
| "Coche adaptado", "coche para discapacitado", "embrague al volante" | **Coche adaptado** | **37** |
| "Apnea", "ronco mucho", "uso máquina para dormir", "CPAP" | Trastornos del sueño | **42** |

## Clasificación de Gravedad para el Nodo Final
El LLM debe marcar como "Crítico" en el vector si identifica los códigos **4, 24, 31 o 37**, ya que estos obligan a realizar el examen médico exclusivamente en la sede de la Intendencia [4, 6, 7].

## Ejemplo de Flujo Interno (Estado del Grafo)
**Usuario:** "Soy hipertenso y uso lentes de contacto".
**Acción del LLM:**
- `tiene_patologias`: true
- `vector_patologias`: [8, 9]
- **Respuesta:** "Comprendido. ¿Qué edad tiene el solicitante?" (Continúa el flujo)

## Fuentes de Referencia
- **codigosdepatologiasab2411.pdf:** Tabla completa de códigos y vigencias [2, 10].
- **Protocolo Agendas y Multas 2019:** Sección de Códigos de Patologías, págs. 31-33 [1, 6].
- **Artículo R.424.190:** Parámetros médicos y causales de denegatoria [11, 12].