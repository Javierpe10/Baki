# BAKI — Pasos que tienes que hacer tú

Todos los comandos se ejecutan en PowerShell desde la carpeta `BAKI\backend` del proyecto.
Las claves se escriben en la consola (entrada oculta) y van al Administrador de credenciales de Windows.
Nunca las pegues en el chat de BAKI.

## 0. Arrancar y apagar BAKI

En el escritorio tienes dos iconos:
- **BAKI**: lo enciende sin abrir ventanas de consola y abre su ventana en Edge. Si ya estaba encendido, solo abre la ventana. Si ha cambiado el código de la interfaz, la recompila solo.
- **Apagar BAKI**: lo detiene por completo, rutinas programadas incluidas.

La primera vez, acepta el permiso de micrófono. Pulsa **Manos libres** y di «Baki, ¿qué hora es?».
Ya no hace falta `npm run dev` ni `uvicorn --reload`.

Si algo falla al arrancar, sale un aviso y el detalle queda en `backend\data\baki_errores.log`.

Para que BAKI arranque al encender el ordenador: pulsa `Win + R`, escribe `shell:startup`, pulsa Enter y copia el icono **BAKI** en la carpeta que se abre.

## 1. Google (Gmail + Calendar) — 10 minutos

1. https://console.cloud.google.com → crea el proyecto «BAKI».
2. «APIs y servicios» → «Biblioteca» → habilita **Gmail API** y **Google Calendar API**.
3. «Pantalla de consentimiento OAuth» → tipo **Interno** → nombre BAKI → guardar.
4. «Credenciales» → «Crear credenciales» → «ID de cliente de OAuth» → tipo **Aplicación de escritorio** → descarga el JSON.
5. Ejecuta (cambia la ruta por la del JSON descargado):

```powershell
..\.venv\Scripts\python.exe -m app.secrets_cli autorizar-google "%USERPROFILE%\Downloads\client_secret_XXXX.json"
```

6. Se abre el navegador: elige la cuenta de empresa y acepta. Después borra el JSON de Descargas.

## 2. GoHighLevel (CRM, Instagram, SMS, redes) — 5 minutos

1. En GHL entra en tu **sub-cuenta** → Settings → **Private Integrations** → «Create new integration» → nombre BAKI.
2. Marca los permisos: contacts (read/write), conversations (read/write), conversations/message (read/write),
   opportunities (read/write), calendars (read/write), calendars/events (read/write), socialplanner/post (read/write),
   socialplanner/account (read), locations (read). Copia el token.
3. Copia el **Location ID** (Settings → Business Profile, o la URL `/location/XXXX/`).
4. Ejecuta y pega ambos cuando los pida:

```powershell
..\.venv\Scripts\python.exe -m app.secrets_cli conectar-ghl
```

Para Instagram: conecta la cuenta profesional de Instagram en GHL → Marketing → Social Planner. BAKI publicará y
responderá DMs a través de GHL.

## 3. n8n (automatizaciones y agentes) — 3 minutos

n8n está instalado en Docker (`BAKI\n8n\docker-compose.yml`) y funciona en **http://localhost:5678**, solo accesible desde este ordenador. Arranca solo cuando Docker está encendido, y el icono BAKI enciende Docker si hace falta. Apagar BAKI no apaga n8n, para que tus automatizaciones sigan funcionando. Los archivos que pongas en `BAKI\n8n\archivos` los ve n8n en la ruta `/files`.

1. Abre http://localhost:5678 y crea tu cuenta de propietario (es local: se queda en tu ordenador).
2. En n8n: **Settings → n8n API → Create an API key**. Copia la clave.
3. Ejecuta esto; como URL escribe `http://localhost:5678` y pega la clave:

```powershell
..\.venv\Scripts\python.exe -m app.secrets_cli conectar-n8n
```

4. Reinicia BAKI con el icono «Apagar BAKI» y luego el icono «BAKI».
5. Las credenciales de las apps (Gmail, WhatsApp, OpenAI/Anthropic, GHL…) se crean dentro de n8n. BAKI no las ve: cuando cree un flujo te dirá qué credencial asignar a cada nodo.

## 4. Voz natural (opcional)

**ElevenLabs:** crea una API key en elevenlabs.io → Profile → API Keys, y ejecuta:

```powershell
..\.venv\Scripts\python.exe -m app.secrets_cli conectar-elevenlabs
```

**Servidor local (gratis):** cualquier servidor TTS local compatible con OpenAI (`/v1/audio/speech`), por ejemplo
Kokoro-FastAPI. Arráncalo y pon en `backend\data\baki_config.json`:
`"tts_local_url": "http://127.0.0.1:8880"` y `"tts_local_voz": "ef_dora"`.

**Sin nada:** Edge usa voces neurales «Microsoft … Online (Natural)» en español, bastante buenas.

Reinicia BAKI tras conectar algo (cierra la ventana minimizada de Python y vuelve a ejecutar el paso 0).

## 5. Ajustes (archivo `backend\data\baki_config.json`)

- `carpetas_aprobadas`: carpetas donde BAKI lee y organiza sin preguntar.
- `modelo`: también se cambia desde el selector de la interfaz.
- `carpeta_proyectos`: dónde crea los proyectos el programador (por defecto `Desktop\Proyectos`).
- `nombre_usuario`, `elevenlabs_voz_id`.
