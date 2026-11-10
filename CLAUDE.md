# BAKI — mapa del proyecto

Asistente personal de Javier, por voz y por texto, en Windows. También construye: automatizaciones en n8n, agentes para empresas y proyectos de código. Su cerebro es el Claude Agent SDK, que usa el login de Claude Pro (no hay API key). Habla en español con Javier.

## Dónde está cada cosa
- `backend/app/main.py`: FastAPI en 127.0.0.1:8001. Expone el WebSocket `/ws` (agente), `/tts`, `/estado`, `/config`, los paneles (`/skills`, `/conversaciones` con abrir y renombrar, `/uso`, `/tareas`) y sirve `frontend/dist`. Solo habla una ventana a la vez (campo `hablar` en cada evento). Las rutas `/chat` y `/permissions/*` son el flujo antiguo; se mantienen porque sus tests siguen vigentes.
- `backend/app/agente/`: el agente.
  - `sesion.py`: ClaudeSDKClient, prompt de sistema, streaming, rutinas.
  - `politica.py`: única puerta de permisos (hook PreToolUse + can_use_tool).
  - `aprobaciones.py`: cola de aprobaciones con huella SHA-256, auditoría y aprobación por grupo.
  - `registro.py`: decorador `@herramienta(nombre, desc, esquema, nivel, resumen)`.
  - `rutas.py`: rutas absolutas y zonas protegidas.
  - `config.py`: rutas del proyecto y `baki_config.json`.
  - `contexto.py`: enlace entre las herramientas y la sesión.
  - `panel.py`: datos de solo lectura para la interfaz (skills, conversaciones del SDK, consumo de hoy).
- `backend/app/agente/herramientas/`: un archivo por área (`archivos`, `sistema`, `web`, `memoria`, `google`, `ghl`, `n8n`, `rutinas`, `programador`). Una herramienta nueva se registra en `herramientas/__init__.py`.
- `backend/app/integraciones/`: el único sitio que lee secretos (`google_auth`, `ghl_cliente`, `n8n_cliente`, `tts`). Un test lo vigila.
- `backend/app/secrets_store.py` y `secrets_cli.py`: secretos en el Administrador de credenciales de Windows (`baki:<servicio>:<nombre>`).
- `backend/data/`: configuración, sesión, auditoría, consumo y rutinas. Es zona protegida para el agente.
  - `plugin_baki/skills/`: skills que usa BAKI mientras funciona.
- `.claude/skills/`: skills para desarrollar BAKI con Claude Code (tdd, grill-me, grilling, codebase-design, find-skills).
- `frontend/src/`: React + Vite, diseño «Command Center».
  - `useBaki.ts`: toda la lógica (WebSocket, voz, aprobaciones, conversaciones, tareas, uso).
  - `App.tsx`: maqueta (cabecera, menú, centro, panel derecho, barra de voz).
  - `components/`: `Marco.tsx` (cabecera, menú, panel derecho, barra de voz), `Chat.tsx` (chat y compositor multilínea), `Vistas.tsx` (Dashboard, Conversaciones, Tareas, Skills, Conectores), `Markdown.tsx` (render seguro, sin HTML crudo), `Iconos.tsx`.
  - `lib/voz.ts`: STT, TTS y filtro anti-eco. `lib/api.ts`: tipos y llamadas.
  - BAKI solo habla si la orden fue por voz.
- `knowledge/BAKI Knowledge/`: bóveda de Obsidian (memoria de BAKI).
- `n8n/docker-compose.yml`: n8n local en Docker, accesible solo desde este ordenador en `127.0.0.1:5678`, con reinicio automático y datos en el volumen `n8n_data`. `n8n/archivos` se monta en `/files`. `iniciar_baki.ps1` enciende Docker; `apagar_baki.ps1` no para n8n.
- `docs/BAKI_estado_2026-11-08.md`: estado actual. Hay que mantenerlo al día con cada cambio importante.
- `docs/GUIA_CONEXIONES.md`: pasos manuales de Javier.
- `GUIA_SKILLS.md`: qué hace cada skill y cómo se activa. Actualízala al añadir o quitar skills.

## Comandos (PowerShell)
- Tests: `cd backend; ..\.venv\Scripts\python.exe -m pytest tests -q` (esperado: 155 passed, 1 skipped)
- Interfaz: `cd frontend; npm run build; npx eslint src`
- Arrancar: icono «BAKI» del escritorio o `iniciar_baki.ps1` (backend oculto, logs en `backend/data/baki_*.log`, recompila la interfaz si cambió). Apagar: icono «Apagar BAKI» o `apagar_baki.ps1`. Tras cambiar el backend, apaga y vuelve a arrancar. No uses `--reload`: se cuelga.
- Los `.ps1` se guardan en UTF-8 con BOM: PowerShell 5.1 rompe las tildes sin él.

## Repositorio público
- https://github.com/Javierpe10/Baki (público, sin licencia: todos los derechos reservados).
- Antes de cada commit, revisa que no entre nada privado: `backend/data/` (salvo `plugin_baki`), `knowledge/`, `*.jsonl`, `*.log` y las notas internas están en `.gitignore`. No escribas rutas con el usuario de Windows, emails, claves ni nombres de clientes en archivos versionados.
- Los commits usan el email anónimo de GitHub configurado en el repositorio, nunca el Gmail.

## Reglas
- Niveles de permiso:
  - Nivel 1, sin preguntar: leer y consultar.
  - Nivel 2, con aprobación: enviar, publicar, borrar, sobrescribir, ejecutar.
  - Lo que no está en la política se deniega.
  - Toda herramienta nueva declara su nivel y lleva un test en `tests/test_agente.py`.
- El agente arranca con `setting_sources=[]`. Las skills llegan solo como plugin local. Nunca cargues settings del disco en el agente.
- Los secretos nunca van en prompts, logs, auditoría ni archivos del proyecto. Se introducen solo con `secrets_cli`.
- Al cambiar algo, distingue entre diseñado, implementado y probado. Cambios pequeños y verificables. Instalar dependencias en `.venv` está autorizado; actualiza `backend/requirements.txt`.
- Javier prefiere que le señales el punto débil de cada propuesta antes de darle la razón. Explícale paso a paso solo lo que tenga que hacer él.
- `main.py` y algunos tests usan saltos de línea CRLF: respétalos al editar.
