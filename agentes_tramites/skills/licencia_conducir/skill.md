# Skill: licencia_conducir

## Cuándo usarla

Usar para consultas sobre primera licencia, renovación, duplicado u
homologación de licencias de conducir.

## Implementación

La conversación está coordinada por LangGraph:

1. `handler.py` adapta el contrato general de la aplicación.
2. `graph.py` ejecuta los nodos de extracción, decisión y salida.
3. `matcher.py` compara el estado con `hojas_terminales.json`.
4. El nodo terminal carga un Markdown desde `documentos_terminales/`.
5. `document_qa.py` resume el trámite y responde preguntas posteriores usando
   el documento completo y el historial reciente.

La primera versión usa extracción determinista dentro de la skill. El LLM del
router puede aportar campos iniciales, pero no decide la hoja terminal.

## Fuentes

- `hojas_terminales.json`: condiciones estructuradas de las hojas.
- `documentos_terminales/*.md`: información exacta de cada caso.
- `insumos/insumos_licencia_cond.txt`: insumo original del que fueron
  extraídos los archivos.

## Contrato de salida

```json
{
  "status": "need_input | document_qa | final",
  "question": "texto o null",
  "answer": "Resumen, respuesta documental o mensaje de falta de cobertura",
  "state_updates": {},
  "terminal_leaf_id": "identificador o null",
  "terminal_document": "archivo.md o null"
}
```

## Límites

- Sólo cubre las ocho hojas terminales presentes en el insumo.
- Usa el LLM para resumir y responder únicamente sobre el Markdown terminal.
- Conserva hasta ocho mensajes recientes como contexto de conversación.
- Una combinación no cubierta termina con un mensaje explícito.
