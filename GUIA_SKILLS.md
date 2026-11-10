# Guía de skills de BAKI

Actualizada: 8 de noviembre de 2026.

Hay dos grupos de skills, en sitios distintos:

| Grupo | Dónde están | Quién las usa |
|---|---|---|
| **A. Skills de BAKI** (13) | `backend\data\plugin_baki\skills\` | BAKI, cuando le hablas o escribes en su interfaz |
| **B. Skills de desarrollo** (5) | `.claude\skills\` | Claude Code, cuando trabajamos en el código de BAKI desde VS Code |

**Cómo funciona la activación:**
- **Automática:** BAKI lee la descripción de cada skill y la usa cuando tu petición encaja. No tienes que decir su nombre.
- **Por nombre:** si quieres forzar una, di «usa la skill *nombre*», por ejemplo «usa idea-refine». Funciona igual por voz y por escrito.
- La interfaz de BAKI **no tiene comandos con barra** (`/algo`): se piden con palabras. Las barras solo existen en Claude Code (grupo B).

---

## Resumen rápido (grupo A)

| Skill | Para qué | ¿Automática? | Frase para activarla |
|---|---|---|---|
| proyecto-nuevo | Llevar un proyecto de la idea a algo que funciona | Sí | «Nuevo proyecto: …» |
| idea-refine | Mejorar una idea: variantes, supuestos y «lo que no haremos» | Sí | «Tengo una idea: … ayúdame a refinarla» |
| grilling | Cuestionarte un plan por rondas, con recomendación en cada pregunta | Sí | «Grill me», «cuestióname esto» |
| grill-me | Atajo que solo lanza `grilling` | **No** (ver nota) | Di «grill me»: BAKI usa `grilling` |
| spec-driven-development | Escribir la especificación (SPEC.md) antes de programar | Sí | «Haz la especificación de …» |
| planning-and-task-breakdown | Dividir el trabajo en tareas pequeñas verificables | Sí | «Planifica las tareas de …» |
| n8n-automatizacion | Diseñar, crear, probar y activar flujos en n8n | Sí | «Créame en n8n un flujo que …» |
| agente-empresa | Diseñar y construir un agente de IA para un cliente | Sí | «Diseña un agente para la empresa X» |
| tdd | Programar con el test primero | Sí | «Hazlo con tests primero» |
| codebase-design | Diseñar módulos limpios y fáciles de probar | Sí | «¿Cómo estructuro este código?» |
| security-and-hardening | Revisión de seguridad y RGPD antes de entregar | Sí | «Revisa la seguridad de …» |
| debugging-and-error-recovery | Método para encontrar y arreglar fallos | Sí | «Esto falla: …» |
| find-skills | Buscar skills nuevas en internet | Sí | «¿Hay alguna skill para …?» |

---

## A. Skills de BAKI, una a una

### 1. proyecto-nuevo
- **Función:** guía completa de un proyecto en 4 fases.
  1. Entender y cuestionar: investiga, refina la idea y te hace preguntas.
  2. Propuesta: BRIEF.md y, si hay código, SPEC.md y plan de tareas.
  3. Construcción: código con el programador, flujos de n8n o el CRM.
  4. Verificación: lo prueba antes de darlo por terminado.
  Al final te propone 2 o 3 mejoras que no hayas pedido.
- **Ejemplo:** «Nuevo proyecto: quiero vender a gimnasios un sistema que reactive a los socios que dejan de venir.»
- **Activación:** automática con «nuevo proyecto», «quiero montar…», «ayúdame con un proyecto».
- **Dónde deja los archivos:** `%USERPROFILE%\Desktop\Proyectos\<nombre>\`.

### 2. idea-refine (Addy Osmani)
- **Función:** parte de una idea vaga y la convierte en un documento de una página. Plantea el problema, genera 5-8 variantes, las agrupa en 2-3 direcciones, señala los supuestos sin comprobar y cierra con una lista de «lo que NO haremos».
- **Ejemplo:** «Tengo una idea: un agente que conteste reseñas de Google para restaurantes. Refínala.»
- **Activación:** automática cuando pides ideas o la idea es vaga; también «refina esta idea», «dame ideas para…».
- **Nota:** te hace las preguntas en el chat. Guarda el documento solo si se lo confirmas.

### 3. grilling (Matt Pocock)
- **Función:** te interroga por rondas hasta que no quede nada sin decidir. Cada pregunta trae su recomendación; si estás de acuerdo, basta con decir «sí». Busca por su cuenta lo que puede averiguar en lugar de preguntártelo.
- **Ejemplo:** «Grill me: quiero cobrar 300 € al mes por un agente de WhatsApp para clínicas dentales.»
- **Activación:** automática con «grill me», «cuestióname», «ponme a prueba este plan», y antes de decisiones grandes dentro de `proyecto-nuevo`.

### 4. grill-me (Matt Pocock)
- **Función:** atajo que solo lanza `grilling`.
- **Activación:** **no automática**. Su autor la marcó para que solo la active una persona.
- **Cómo usarla en BAKI:** di «grill me» y BAKI usa `grilling` directamente. El resultado es el mismo; está probado en una conversación real.

### 5. spec-driven-development (Addy Osmani)
- **Función:** antes de programar, escribe un SPEC.md con:
  - Supuestos, objetivo, tecnología y comandos.
  - Estructura del proyecto, estilo de código y estrategia de tests.
  - Límites: siempre, preguntar antes, nunca.
  - Criterios de éxito.
  Después **se para y espera tu aprobación**.
- **Ejemplo:** «Haz la especificación de una web de reservas para la clínica Sonrisa.»
- **Activación:** automática en proyectos con código; también «escribe la especificación», «haz un SPEC».

### 6. planning-and-task-breakdown (Addy Osmani)
- **Función:** convierte la especificación aprobada en un plan (`tasks/plan.md`) y una lista de tareas pequeñas (`tasks/todo.md`). Cada tarea tiene su forma de comprobarla, y hay puntos de control cada 2-3 tareas.
- **Ejemplo:** «Aprobado el SPEC. Planifica las tareas.»
- **Activación:** automática tras aprobar una especificación; también «planifica», «divide esto en tareas».

### 7. n8n-automatizacion (propia de BAKI)
- **Función:**
  1. Diseña el flujo nodo a nodo.
  2. Mira si ya existe uno parecido.
  3. Lo crea inactivo y lo prueba por su webhook.
  4. Revisa las ejecuciones y corrige los fallos.
  5. Lo activa con tu aprobación.
  Te dice qué credencial asignar en n8n a cada nodo (BAKI nunca ve tus claves de n8n).
- **Ejemplo:** «Créame en n8n un flujo que, cuando entre un lead en GoHighLevel, le mande un WhatsApp de bienvenida y me avise por email.»
- **Activación:** automática con «automatización», «flujo», «workflow», «en n8n…».
- **Requisito:** n8n conectado (ver `docs\GUIA_CONEXIONES.md`, paso 3).

### 8. agente-empresa (propia de BAKI)
- **Función:**
  1. Investiga la empresa: web, reseñas, competencia.
  2. Detecta los 3-5 procesos que más compensa automatizar.
  3. Elige la arquitectura: n8n, GoHighLevel o código propio.
  4. Entrega PROPUESTA.md (con precio sugerido), PROMPT_AGENTE.md, la implementación y un plan de pruebas que incluye intentos de engañar al agente.
  5. Pasa la revisión de seguridad antes de entregar.
- **Ejemplo:** «Diseña un agente para la inmobiliaria Casas del Sur, su web es casasdelsur.es.»
- **Activación:** automática con «agente para la empresa X», «propuesta de IA para un cliente», «automatiza el negocio de X».
- **Regla:** nunca envía nada al cliente sin tu aprobación.

### 9. tdd (Matt Pocock)
- **Función:** programa en ciclos cortos: primero un test que falla, después el código mínimo para que pase. Antes de escribir tests acuerda contigo qué partes se van a probar.
- **Ejemplo:** «Programa el cálculo de comisiones con tests primero.»
- **Activación:** automática cuando hay lógica que probar, sobre todo dentro de `programar_proyecto`; también «hazlo con TDD».

### 10. codebase-design (Matt Pocock)
- **Función:** vocabulario y criterios para diseñar código fácil de mantener y de probar: módulos con poca interfaz y mucha lógica dentro, y fronteras claras entre partes. La usan `tdd` y el programador.
- **Ejemplo:** «Este proyecto se ha vuelto un lío, ¿cómo lo reorganizo?»
- **Activación:** automática al diseñar o reorganizar código.

### 11. security-and-hardening (Addy Osmani)
- **Función:** revisión de seguridad completa:
  - Mapa de amenazas.
  - Validación de entradas y protección contra peticiones a la red interna.
  - Secretos, dependencias y cookies.
  - **Datos personales y RGPD**.
  - Riesgos de agentes con IA, como la inyección de prompt.
- **Ejemplo:** «Revisa la seguridad del agente de la clínica antes de entregarlo.»
- **Activación:** automática antes de entregar algo con datos de clientes, credenciales, webhooks o una IA de cara al público; también «revisa la seguridad».

### 12. debugging-and-error-recovery (Addy Osmani)
- **Función:** método para fallos:
  1. Parar y conservar las pruebas del error.
  2. Reproducirlo.
  3. Localizarlo.
  4. Arreglar la causa, no el síntoma.
  5. Añadir un test para que no vuelva.
  6. Verificar.
  Trata los mensajes de error como datos, no como órdenes.
- **Ejemplo:** «El flujo de n8n de bienvenida ha fallado esta noche, arréglalo.»
- **Activación:** automática cuando algo falla.

### 13. find-skills (Vercel)
- **Función:** busca en skills.sh skills nuevas para una necesidad concreta, comprobando su popularidad y su autor.
- **Ejemplo:** «¿Hay alguna skill para hacer presentaciones comerciales?»
- **Activación:** automática con «¿hay una skill para…?», «busca una skill…».
- **Importante:** BAKI no puede instalar skills por sí mismo. Su carpeta de skills está protegida y el comando de instalación pediría tu aprobación. Lo correcto es pedírmelo en Claude Code, para que revise el contenido antes de añadirla.

---

## B. Skills de desarrollo (Claude Code en VS Code)

Solo existen cuando abres Claude Code en la carpeta `BAKI`. Aquí sí hay comandos con barra.

| Skill | Para qué | ¿Automática? | Cómo activarla |
|---|---|---|---|
| tdd | Test primero al cambiar el código de BAKI | Sí | `/tdd` o «hazlo con TDD» |
| grilling | Cuestionar un cambio antes de hacerlo | Sí | «grill me» o `/grilling` |
| grill-me | Atajo de grilling | **No** | Solo escribiendo `/grill-me` |
| codebase-design | Diseñar módulos y dónde poner los tests | Sí | `/codebase-design` |
| find-skills | Buscar skills nuevas | Sí | `/find-skills` o «¿hay una skill para…?» |

Claude Code trae además de serie `/code-review`, `/security-review` y `/simplify`.

---

## Combinaciones útiles

- **Idea de negocio nueva:** «Tengo una idea: … refínala y luego grill me». Usa idea-refine y después grilling.
- **Proyecto con código para un cliente:** «Nuevo proyecto para la empresa X». Recorre proyecto-nuevo, especificación, plan, el programador con tdd, la revisión de seguridad y la entrega.
- **Automatización rápida:** «En n8n, cuando pase X haz Y». Usa n8n-automatizacion y, si falla, debugging.

## Procedencia

| Skills | Origen | Licencia |
|---|---|---|
| tdd, grill-me, grilling, codebase-design | github.com/mattpocock/skills | MIT |
| find-skills | github.com/vercel-labs/skills | MIT |
| idea-refine, spec-driven-development, planning-and-task-breakdown, security-and-hardening, debugging-and-error-recovery | github.com/addyosmani/agent-skills | MIT |
| proyecto-nuevo, n8n-automatizacion, agente-empresa | Escritas para BAKI | Propias |

El detalle de versiones está en `backend\data\plugin_baki\ORIGEN.md`. Antes de instalarse, se revisó el contenido de todas.
