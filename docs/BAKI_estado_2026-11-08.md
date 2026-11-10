# BAKI — Estado del proyecto (8 de noviembre de 2026)

Sustituye como documento principal a `BAKI_estado_2026-11-07.md` (se conserva como histórico).

## 1. Qué cambió

BAKI pasó de «Claude propone un JSON y el backend ejecuta una herramienta» a un **agente real sobre el
Claude Agent SDK (Python)**, que encadena herramientas y conserva tu política de permisos de dos niveles.

| Capacidad | Estado | Evidencia |
|---|---|---|
| Agente con 42 herramientas (SDK + MCP en proceso) | Probado | Prueba real por WebSocket: listar Escritorio (auto) y crear archivo (aprobación) |
| Política de 2 niveles (hook PreToolUse + can_use_tool) | Probado | `tests/test_agente.py` + prueba real |
| Aprobación desde la interfaz y por voz («sí» / «no») | Probado (botón) / Implementado (voz) | Prueba en navegador con botón Aprobar |
| Respuesta en streaming + voz frase a frase | Implementado | Build OK; voz no probada en el panel embebido |
| Manos libres con palabra «Baki», barge-in y ventana de conversación | Implementado | Requiere Edge/Chrome real (micrófono) |
| Filtro anti-eco (BAKI no se oye a sí mismo) | Probado (detector, 10 casos) | Falta prueba con micrófono y altavoces reales |
| Una sola ventana habla aunque haya varias abiertas | Probado | Dos pestañas a la vez |
| Iconos de escritorio «BAKI» y «Apagar BAKI» | Probado (arranque) | Backend oculto; logs en backend/data/baki_*.log |
| Interfaz «Command Center»: menú (Centro de mando, Dashboard, Conversaciones, Tareas, Skills, Conectores), uso de Claude, tareas de la conversación, fecha y hora, barra de voz | Probado | Revisada en navegador; carga el historial de la conversación |
| Respuesta hablada solo si la orden fue por voz | Probado | Orden escrita: sin voz |
| Compositor multilínea (Mayús+Intro, listas automáticas, cursor conservado) | Probado (listas) / Implementado (cursor al cambiar de ventana) | |
| Cambiar entre conversaciones anteriores | Implementado | Endpoint probado; usa el historial del SDK |
| Tests | **154 passed, 1 skipped** (8 nov, tarde) | |
| Conversación persistente (se reanuda tras reiniciar) | Implementado | `backend/data/sesion.json` |
| Archivos: leer (txt, código, docx, pdf), listar, buscar, crear, editar, sobrescribir con copia, mover, copiar, papelera | Probado (unit + real) | |
| PowerShell, abrir apps/webs/archivos, portapapeles, info del sistema | Implementado | PowerShell siempre con aprobación |
| Scraping `leer_web` con protección SSRF | Probado | Tests SSRF + prueba real |
| WebSearch / WebFetch | Implementado | Integradas de Claude |
| Gmail (buscar, leer, borrador, enviar, papelera) y Calendar | Implementado, sin conectar | Falta OAuth (paso manual de Javier) |
| CRM GoHighLevel: contactos, oportunidades, conversaciones (SMS/Email/IG/WhatsApp), redes sociales, API genérica | Implementado, sin conectar | Falta token (paso manual) |
| Rutinas programadas (solo lectura + borradores) | Probado (unit) | |
| Memoria Obsidian: buscar (auto) y guardar (aprobación) | Implementado | |
| Voz ElevenLabs / servidor local / navegador | Implementado | Por defecto navegador |
| Skills en BAKI (plugin local aislado, 13): proyecto-nuevo, grill-me/grilling, n8n-automatizacion, agente-empresa, tdd, codebase-design, find-skills + de addyosmani/agent-skills: idea-refine, spec-driven-development, planning-and-task-breakdown, security-and-hardening, debugging-and-error-recovery | Probado | grill-me lanzó su ronda de preguntas en una prueba real |
| n8n: listar, ver, crear, modificar, activar, borrar, ejecuciones, webhooks | Implementado, sin conectar | Falta URL + API key (paso manual) |
| Subagente `programar_proyecto` (Claude Code dentro de una carpeta) | Probado | Prueba real: creó código + tests y los ejecutó tras aprobar el comando |
| Aprobación en bloque de los comandos de una tarea | Probado (unit + real) | |
| Tests | **148 passed, 1 skipped** (Windows, 8 nov) | |

## 2. Arquitectura

```
Edge (127.0.0.1:8001)  ──WebSocket /ws──►  FastAPI  ──►  ClaudeSDKClient (Sonnet 5.5, login Claude Pro)
  voz (STT navegador)                       │              ├─ hook PreToolUse  → politica.evaluar()
  voz (TTS /tts)                            │              ├─ can_use_tool     → GestorAprobaciones (espera tu OK)
  tarjetas de aprobación                    │              └─ MCP "baki" en proceso → 42 herramientas
                                            └─ planificador de rutinas (cada 20 s)
```

- `backend/app/agente/`: `config.py`, `rutas.py`, `registro.py`, `politica.py`, `aprobaciones.py`, `sesion.py`, `herramientas/*`.
- `backend/app/integraciones/`: única capa que lee secretos (Google, GHL, ElevenLabs). Un test lo vigila.
- `setting_sources=[]` y `tools=["WebSearch","WebFetch"]`: ningún settings.json, CLAUDE.md ni herramienta integrada (Bash, Write…) entra en el agente.
- Zonas protegidas que el agente no puede modificar: `backend/app`, `backend/tests`, `.venv`, `~/.ssh`, `~/.claude`, credenciales de Windows, `C:\Windows`; archivos `.env`, `.pem`, `.key`…
- La interfaz compilada la sirve el backend en `http://127.0.0.1:8001` (un solo proceso). En desarrollo, Vite en 5173 sigue funcionando.
- El flujo antiguo (`/chat`, `/permissions/*`) se mantiene por compatibilidad y sus tests siguen pasando.

### Construcción (añadido el 8 nov, tarde)
- Skills en `backend/data/plugin_baki/skills/` como plugin local: el agente las usa con la herramienta `Skill` sin cargar ningún settings.json ni hook del disco.
- `programar_proyecto`: subagente con herramientas de Claude Code (Read/Write/Edit/Glob/Grep/Bash) encerrado en una carpeta (por defecto `Desktop\Proyectos\<nombre>`). Dentro escribe libremente; fuera no lee ni escribe; cada comando pide aprobación (o «aprobar todos los de esta tarea»). No carga la configuración `.claude` del proyecto.
- `backend/data` (configuración, auditoría, skills) es zona protegida: el agente no puede ampliarse permisos.

## 3. Niveles

- **Nivel 1 (sin preguntar):** búsquedas web, scraping, leer/listar/buscar en carpetas aprobadas, mover/copiar/crear carpeta dentro de ellas, Gmail leer/buscar/borrador/marcar leído, ver agenda, CRM lecturas y `crm_api` GET, abrir webs/carpetas/documentos/apps conocidas, portapapeles, memoria (buscar), listar rutinas.
- **Nivel 2 (tu aprobación con los argumentos exactos, caduca a los 5 min):** crear/sobrescribir/editar/borrar archivos, cualquier cosa fuera de carpetas aprobadas, PowerShell, ejecutables, enviar correo, papelera Gmail, crear/modificar/borrar eventos, crear/actualizar contactos, enviar mensajes, publicar en redes, `crm_api` no-GET, guardar memoria, crear/borrar rutinas.
- **Denegado:** cualquier herramienta fuera de la política.
- **Rutinas:** solo nivel 1; lo demás queda en el informe como «pendiente de tu aprobación».

## 4. Riesgos conocidos

1. Un proceso local malicioso puede hablar con 127.0.0.1:8001 (mismo modelo de amenaza que antes; Host/Origin frenan webs y DNS rebinding).
2. El eco de la voz puede activar el reconocimiento: mientras BAKI habla solo se aceptan «Baki…» o «para».
3. `leer_web` resuelve DNS antes de conectar; un rebinding entre ambas operaciones es teórico.
4. El esquema de publicación en redes de GHL puede variar; si falla, el agente recibe el error y puede usar `crm_api`.
5. Cuota Claude Pro: Sonnet por defecto. Consumo en `backend/data/consumo.jsonl`.

## 5. Pendiente (requiere a Javier)

Ver `docs/GUIA_CONEXIONES.md`: Google OAuth, GoHighLevel, ElevenLabs (opcional), acceso directo.
