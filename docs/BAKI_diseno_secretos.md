# BAKI — Diseño de gestión de secretos

Estado: **almacén y consola implementados** (`secrets_store.py`, `secrets_cli.py`) con pruebas en Linux. Pendiente: flujo OAuth de Google y revisión del usuario.
Fecha: 7 de noviembre de 2026.
Origen: fase 7 del plan («gestión de credenciales y secretos segura»), adelantada antes de la fase 5 por decisión del usuario.

---

## 1. Alcance

Credenciales necesarias para integraciones externas. La primera es Google Workspace (Gmail y Calendar) de la cuenta de empresa.

Incluye:
- Almacenamiento de credenciales y tokens OAuth.
- Acceso a credenciales por parte de las herramientas.
- Pruebas que impidan que un secreto salga del backend.

No incluye:
- Integraciones concretas (Gmail, Calendar, Instagram). Van después, cada una con su propia aprobación.
- Rotación automática de credenciales.

---

## 2. Principios

1. **Un secreto nunca entra en un prompt de Claude.** Ni en el mensaje del usuario, ni en el contexto de Obsidian, ni en el historial, ni en el resultado de una herramienta.
2. **Un secreto nunca se escribe en un archivo del proyecto, en el repositorio, en los logs ni en la auditoría.**
3. **El usuario nunca escribe un secreto en el chat.** Se introduce en una consola local con entrada oculta.
4. **Solo el manejador de la herramienta que lo necesita puede leer un secreto.** Ningún otro componente lo lee.
5. **Sin almacén disponible, la integración no se ejecuta.** Fallo cerrado.

Los principios 1 a 3 son propuestas mías, no están literalmente en el plan. Las marco como tales.

---

## 3. Almacenamiento

- **Dónde:** Administrador de credenciales de Windows, mediante la librería `keyring`. [Likely] No requiere ningún archivo en el proyecto.
- **Por qué:** sin él, las credenciales quedarían en texto plano en el disco. Es una dependencia nueva, justificada por la regla 4 del plan.
- **Nombres:** `baki:<servicio>:<nombre>`, por ejemplo `baki:google:oauth_client` o `baki:google:refresh_token`.
- **Contenido:** solo el valor del secreto. No se guardan fechas, ni logs, ni la respuesta completa del proveedor.

---

## 4. Interfaz

Un módulo `backend/app/secrets_store.py` con tres funciones:

- `guardar(nombre, valor)`
- `leer(nombre) -> str`
- `borrar(nombre)`

Un script de consola `backend/app/secrets_cli.py`:

- `python -m app.secrets_cli guardar baki:google:oauth_client` pide el valor con entrada oculta (`getpass`).
- `python -m app.secrets_cli borrar baki:google:refresh_token`
- `python -m app.secrets_cli listar` muestra solo los nombres, nunca los valores.

No hay endpoint HTTP para guardar ni leer secretos. Ni `main.py` ni el frontend tienen acceso a `leer`.

---

## 5. Quién puede leer un secreto

- Solo funciones de la capa de integración que ejecutan una operación ya aprobada.
- `ClaudeGateway`, `ToolRegistry`, `ToolExecutor`, `PermissionManager` y `main.py` no pueden llamar a `leer`. Esto se comprueba con una prueba que busca importaciones de `secrets_store` fuera de la capa de integración.

---

## 6. Restricciones de salida

Ningún dato que salga del backend puede contener un secreto:

- **Prompts a Claude:** se comprueba con una prueba que construye el prompt completo de una llamada con integración activa y verifica que el valor no aparece.
- **Respuestas HTTP:** los errores se reemplazan por mensajes genéricos cuando puedan contener un token. [Guessing] Algunas librerías de Google incluyen URLs o cabeceras en sus excepciones, y eso no lo he comprobado.
- **Logs de uso** (`usage_log.jsonl`) y **auditoría** (`permissions_audit.jsonl`): solo registran tamaños, contadores, rutas y motivos. Nunca valores de secretos.
- **Mensajes de excepción:** antes de mostrarse, se pasan por un filtro que sustituye cualquier cadena que coincida con un valor guardado.

---

## 7. OAuth para Google Workspace

- **Cliente OAuth de tipo aplicación de escritorio.** El `client_secret` también se guarda en el almacén.
- **Alcances mínimos:** solo los necesarios para cada operación aprobada. Empezar por `calendar.events` y `gmail.send`. Leer el correo no se incluye hasta que se pida expresamente. [Likely] Google clasifica algunos alcances como sensibles y exige revisión.
- **Flujo de autorización:** se ejecuta una sola vez, desde la consola local (`python -m app.secrets_cli autorizar google`). Abre el navegador, el usuario autoriza, y el token de actualización se guarda en el almacén.
- **Revocación:** en la cuenta de Google, o con `borrar` en la consola de BAKI.

---

## 8. Requisitos previos del usuario (fuera del código)

1. Confirmar si tiene permisos de administrador en el Workspace o si necesita aprobación del administrador. [Likely] Puede bloquear el paso 3.
2. Crear un proyecto en Google Cloud Console.
3. Activar la API de Gmail y la API de Google Calendar.
4. Configurar la pantalla de consentimiento OAuth. Si la cuenta es de Workspace, el tipo «interno» evita la revisión de Google. [Likely]
5. Crear un cliente OAuth de tipo «aplicación de escritorio» y guardar sus datos con `guardar`.

---

## 9. Pruebas previstas

- `guardar` y `leer` devuelven el mismo valor, con un almacén en memoria para las pruebas.
- Sin almacén disponible, la integración falla con un error claro y no ejecuta nada.
- El valor de un secreto no aparece en el prompt, en la auditoría, en el registro de uso ni en un mensaje de error.
- Ningún módulo fuera de la capa de integración importa `leer`.
- `listar` no muestra valores.

---

## 10. Pendiente de decisión

- Confirmar que los secretos se introducen solo con la consola local, nunca en el chat. Esta es una decisión de diseño mía que necesita tu visto bueno.
- Confirmar el paso 1 de requisitos previos (administrador del Workspace).
