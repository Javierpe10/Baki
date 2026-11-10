---
name: proyecto-nuevo
description: Lleva un proyecto nuevo de la idea a algo funcionando. Úsala cuando Javier diga "nuevo proyecto", "ayúdame con un proyecto", "quiero montar/crear/construir X", o pida ideas y propuestas para un proyecto.
---

# Proyecto nuevo: idea → decisión → construcción → verificación

Trabajas para Javier, que está creando una agencia de IA. Tu objetivo es entregar resultados, no solo opiniones.

## Fase 1 — Entender y cuestionar (obligatoria salvo que Javier diga "no me preguntes")
1. Busca en la memoria (`buscar_memoria`) si ya hay contexto del proyecto o del cliente.
2. Si hay hechos que puedes averiguar tú (web del cliente, competencia, precios, tecnología), averígualos con WebSearch / leer_web ANTES de preguntar.
3. Si la idea aún es vaga o Javier pide ideas, usa `baki:idea-refine` (5-8 variantes, supuestos ocultos y lista de "lo que NO haremos"). En BAKI no existe AskUserQuestion: haz las preguntas en el chat. Ignora su script de carpeta; guarda el resultado con `crear_archivo` en la carpeta del proyecto.
4. Usa la skill `baki:grilling` para cuestionar la idea por rondas. Cada pregunta lleva tu recomendación. Señala el punto débil de cada opción (Javier lo prefiere a que le des la razón).
5. Termina la fase con un resumen de decisiones y espera su "sí".

## Fase 2 — Propuesta
Si el proyecto lleva código, sigue `baki:spec-driven-development` (SPEC.md con supuestos, criterios de éxito y límites; espera aprobación) y después `baki:planning-and-task-breakdown` (tareas pequeñas y verificables). Además, o si no hay código, escribe en la carpeta del proyecto (`<carpeta de proyectos>\<nombre>\BRIEF.md` (normalmente `%USERPROFILE%\Desktop\Proyectos`)) con `crear_archivo`:
- Objetivo y métrica de éxito.
- Usuario/cliente y problema.
- Alcance v1 (lo mínimo que aporta valor) y lo que queda fuera.
- Arquitectura y herramientas (n8n, Claude Agent SDK, GHL, web…), con alternativas descartadas y por qué.
- Riesgos y coste estimado (tiempo, dinero, mantenimiento).
- Plan por pasos verificables.
Da 2-3 ideas de mejora o monetización que Javier no haya pedido, marcadas como PROPUESTA.

## Fase 3 — Construcción
- Código: usa `programar_proyecto` con la carpeta del proyecto y una instrucción completa (incluye el contenido del BRIEF y el paso concreto). Pide que trabaje con TDD cuando haya lógica.
- Automatizaciones: usa la skill `baki:n8n-automatizacion`.
- Agentes para empresas: usa la skill `baki:agente-empresa`.
- CRM/marketing: herramientas `crm_*` y `redes_*`.
Avanza paso a paso; tras cada paso comprueba que funciona antes de seguir.

## Fase 4 — Verificación y cierre
- Ejecuta o prueba lo construido (tests, ejecución de n8n, petición de prueba). Si algo falla, sigue `baki:debugging-and-error-recovery` (reproducir, localizar, arreglar la causa, añadir un test).
- Si maneja datos de clientes, credenciales, webhooks o un LLM de cara al público, pasa `baki:security-and-hardening` antes de entregar (en clínicas y salud, el RGPD es crítico).
- Informa: qué funciona (probado), qué está hecho sin probar y qué falta. Nunca digas "terminado" sin una prueba.
- Propón guardar en memoria las decisiones clave (`guardar_memoria`, nota con el nombre del proyecto).
