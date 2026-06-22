# PoC de agentes y skills para trámites

Prueba de concepto local en Python que muestra cómo separar un asistente de
trámites en un orquestador, un registro de skills, estado conversacional,
lógica ejecutable y datos estructurados.

Las skills disponibles son `licencia_conducir` y `permiso_construccion`. La
información incluida es ilustrativa y debe validarse contra la fuente oficial.

## Cómo ejecutarla en VSCode

1. Abrir la carpeta que contiene `.venv`, `.env` y `agentes_tramites` en
   VSCode.
2. Abrir una terminal integrada.
3. Crear un entorno virtual:

   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

4. Instalar dependencias:

   ```powershell
   python -m pip install -r .\agentes_tramites\requirements.txt
   ```

5. Ejecutar:

   ```powershell
   python .\agentes_tramites\app.py
   ```

## Componentes

- `app.py`: interfaz de consola y ciclo conversacional.
- `orchestrator.py`: delegación entre el router y las skills.
- `routers.py`: router por palabras clave, router OpenAI y fallback.
- `skill_registry.py`: catálogo de skills disponibles.
- `skills/skill_registry.json`: metadatos usados para descubrir y enrutar.
- `state.py`: estado en memoria de la conversación.
- `skills/licencia_conducir/skill.md`: contrato y alcance de la skill.
- `skills/licencia_conducir/handler.py`: adaptador al contrato común.
- `skills/licencia_conducir/graph.py`: flujo conversacional con LangGraph.
- `skills/licencia_conducir/matcher.py`: reglas de selección terminal.
- `skills/licencia_conducir/document_qa.py`: resumen y preguntas sobre el
  Markdown mediante OpenAI.
- `skills/licencia_conducir/hojas_terminales.json`: condiciones de las hojas.
- `skills/licencia_conducir/documentos_terminales/`: contenido Markdown final.
- `skills/permiso_construccion/`: skill placeholder para probar el enrutamiento.
- `utils/text.py`: normalización de texto compartida.

## Flujo

1. El orquestador recibe el mensaje.
2. El router consulta `skills/skill_registry.json`, identifica una skill y
   extrae campos iniciales.
3. El registro entrega el handler correspondiente.
4. El handler de licencia ejecuta un grafo que pregunta por datos faltantes.
5. Al completar los campos, el matcher elige una hoja y carga su Markdown.
6. El LLM resume qué debe llevar el ciudadano y permite preguntas posteriores
   basadas exclusivamente en ese documento.

La sesión conserva el documento y los últimos mensajes durante esta fase:

- `finalizar`: cierra el trámite actual.
- `nueva consulta`: limpia el estado y vuelve al orquestador.
- `salir`: termina la aplicación.

El mismo catálogo alimenta al router por palabras clave y al prompt del LLM.
El contrato de la skill usa `status`, `question`, `answer` y `state_updates`.
Esto permite reemplazar componentes sin acoplar la interfaz de consola a una
skill concreta.

## Elegir el router

La aplicación funciona sin API key. El modo predeterminado es local:

```powershell
$env:ROUTER_MODE="keywords"
python app.py
```

Modos disponibles:

- `keywords`: siempre usa reglas locales y no hace llamadas externas.
- `auto`: usa el proveedor LLM cuando su configuración está completa; si no,
  usa reglas.
- `llm`: intenta usar el proveedor configurado y conserva el router local como
  fallback.

Para usar LM Studio:

```env
ROUTER_MODE="llm"
LLM_PROVIDER="lmstudio"
LM_STUDIO_BASE_URL="http://localhost:1234/v1"
LM_STUDIO_API_KEY="lm-studio"
ROUTER_MODEL="identificador-del-modelo-router"
DOCUMENT_MODEL="identificador-del-modelo-documental"
```

Los identificadores deben coincidir exactamente con los publicados por
`http://localhost:1234/v1/models`.

Para usar OpenAI:

```env
ROUTER_MODE="llm"
LLM_PROVIDER="openai"
OPENAI_API_KEY="tu-api-key"
ROUTER_MODEL="modelo-router"
DOCUMENT_MODEL="modelo-documental"
```

El archivo `.env` se busca en la carpeta padre de `agentes_tramites`,
independientemente de la carpeta actual de la terminal. Las claves deben
mantenerse fuera del código y de Git. `OPENAI_MODEL` se conserva como variable
de compatibilidad si no se definen los modelos por rol. El LLM router sólo
selecciona la skill y extrae campos; requisitos y pasos continúan saliendo de
las fuentes locales de cada trámite.

## Agregar una nueva skill

1. Crear `skills/nueva_skill/`.
2. Agregar `skill.md`, `handler.py`, `data.yaml` e `__init__.py`.
3. Exponer en el handler una función con esta firma:

   ```python
   def handle(text: str, current_fields: dict[str, object]) -> dict:
       ...
   ```

4. Agregar una entrada en `skills/skill_registry.json`, incluyendo sus
   metadatos, palabras clave y la ruta `modulo:funcion` del handler.

No es necesario modificar el router ni `build_default_registry()`.

## Evolución futura

- Generar el catálogo y el esquema del router LLM desde el registro de skills.
- Usar RAG para normativa extensa, cambiante o con excepciones.
- Agregar una interfaz web con Streamlit.
- Incorporar tests unitarios y de conversación.
- Agregar logging estructurado, métricas y trazas.
- Persistir sesiones en una base de datos.
- Conectar agenda, identidad y APIs oficiales.
- Versionar fuentes y fechas de vigencia de cada requisito.
- Agregar validación de esquemas con Pydantic.
