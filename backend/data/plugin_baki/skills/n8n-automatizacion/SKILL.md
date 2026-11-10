---
name: n8n-automatizacion
description: Diseña, crea, prueba y activa automatizaciones y agentes de IA en n8n mediante su API. Úsala cuando pidan una automatización, un flujo, un workflow, conectar apps entre sí o "créame en n8n…".
---

# Automatizaciones en n8n

## 1. Diseño (antes de tocar n8n)
- Aclara: disparador (webhook, cron, formulario, nuevo email, nuevo lead en GHL…), pasos, datos de entrada/salida, qué pasa si falla, y quién recibe el resultado.
- Si el flujo es para una empresa concreta, investiga su web y herramientas primero.
- Revisa si ya existe algo parecido: `n8n_listar_workflows` y `n8n_ver_workflow` (reutiliza en lugar de duplicar).
- Explica el diseño en 3-6 líneas (nodo → nodo) y pide visto bueno si hay decisiones abiertas.

## 2. Construcción del JSON
`n8n_crear_workflow` recibe `nombre`, `nodos` (lista) y `conexiones` (objeto). Reglas:
- Cada nodo: `{"name": "...", "type": "n8n-nodes-base.xxx", "typeVersion": N, "position": [x, y], "parameters": {...}}`. Nombres únicos y descriptivos en español. Posiciones separadas 220 px en X.
- `conexiones`: `{"Nombre nodo origen": {"main": [[{"node": "Nombre destino", "type": "main", "index": 0}]]}}`. Las ramas de un IF usan `main[0]` (true) y `main[1]` (false).
- Tipos habituales: `n8n-nodes-base.webhook`, `n8n-nodes-base.scheduleTrigger`, `n8n-nodes-base.manualTrigger`, `n8n-nodes-base.httpRequest`, `n8n-nodes-base.set`, `n8n-nodes-base.if`, `n8n-nodes-base.switch`, `n8n-nodes-base.code` (JavaScript), `n8n-nodes-base.gmail`, `n8n-nodes-base.googleSheets`, `n8n-nodes-base.slack`, `n8n-nodes-base.respondToWebhook`.
- Agentes de IA: `@n8n/n8n-nodes-langchain.agent` con un modelo conectado por la conexión `ai_languageModel` (p. ej. `@n8n/n8n-nodes-langchain.lmChatAnthropic`), memoria por `ai_memory` (`memoryBufferWindow`) y herramientas por `ai_tool`. Esas conexiones van en `conexiones` con la clave del tipo (`"ai_languageModel": [[{...,"type":"ai_languageModel"}]]`) desde el nodo modelo hacia el agente.
- Si no estás seguro del `typeVersion` o los parámetros de un nodo, mira un workflow existente con `n8n_ver_workflow` o usa la versión más baja conocida; n8n la migra.
- Nunca pongas claves ni contraseñas en los parámetros. Las credenciales se crean en la interfaz de n8n; deja el nodo sin credencial y dile a Javier exactamente cuál debe asignar.
- Para lógica de GoHighLevel usa `httpRequest` contra `https://services.leadconnectorhq.com` con la credencial que Javier configure en n8n.

## 3. Prueba
- Crea el workflow inactivo. Si tiene webhook, pruébalo con `n8n_llamar_webhook` usando la ruta de prueba (`modo: "test"`) después de pedir a Javier que pulse "Listen for test event", o actívalo y usa `modo: "produccion"`.
- Revisa `n8n_ejecuciones` y `n8n_ver_ejecucion` para confirmar que cada nodo funcionó. Si falla, corrige con `n8n_actualizar_workflow` y repite.

## 4. Entrega
- Activa solo cuando funcione (`n8n_activar`), con aprobación.
- Informa: qué hace, cómo se dispara (URL del webhook si aplica), qué credenciales faltan, cómo vigilarlo y coste aproximado si usa IA.
- Propón guardar la documentación en memoria o en la carpeta del proyecto.
