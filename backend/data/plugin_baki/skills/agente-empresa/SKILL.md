---
name: agente-empresa
description: Diseña y construye un agente de IA o un sistema de automatización a medida para una empresa concreta (cliente de la agencia). Úsala cuando pidan "un agente para la empresa X", "una propuesta de IA para un cliente" o "automatizar el negocio de X".
---

# Agente de IA para una empresa

## 1. Investigación (hazla tú, no preguntes lo que puedes averiguar)
- Web de la empresa (`leer_web`), redes, reseñas, competencia (WebSearch). Sector, tamaño, servicios, canales de contacto, herramientas visibles (formularios, chat, reservas, CRM).
- Busca en memoria y en el CRM (`crm_buscar_contactos`) si ya es cliente o lead.

## 2. Diagnóstico
Detecta 3-5 procesos repetitivos con más retorno. Para cada uno: tiempo/dinero que se pierde hoy, solución con IA, dificultad (baja/media/alta) e impacto. Prioriza por impacto/dificultad.
Usa `baki:grilling` con Javier para cerrar lo que no se pueda saber desde fuera (volúmenes, herramientas internas, presupuesto).

## 3. Arquitectura recomendada
Elige la opción más simple que funcione y di por qué:
- **n8n + nodo AI Agent**: atención por WhatsApp/Instagram/email, cualificación de leads, respuestas, reservas, informes. Rápido de entregar y fácil de mantener para el cliente.
- **GoHighLevel** (workflows + Conversation AI): si el cliente ya vive en GHL o necesita CRM + embudo.
- **Claude Agent SDK / código propio**: solo si hace falta lógica compleja, datos privados grandes o un producto propio.
Incluye: fuentes de conocimiento (FAQ, catálogo, precios), herramientas que el agente necesita, límites (qué nunca puede hacer), traspaso a humano, métricas y coste mensual estimado.

## 4. Entregables
1. `PROPUESTA.md` en la carpeta de proyectos (`carpeta_proyectos`, normalmente `%USERPROFILE%\Desktop\Proyectos\<empresa>\`) (problema, solución, alcance v1, plazos, precio sugerido con desglose, métricas). Lista para enviar al cliente tras revisión de Javier.
2. El prompt de sistema del agente (`PROMPT_AGENTE.md`): rol, tono de la marca, conocimiento, reglas, cuándo derivar a humano.
3. La implementación: skill `baki:n8n-automatizacion` o `programar_proyecto`.
4. Plan de pruebas con 10 conversaciones/casos reales y resultado esperado, incluidos intentos de abuso (inyección de prompt, pedir datos de otros pacientes o clientes).
5. Revisión con `baki:security-and-hardening` (secciones de LLM y datos personales) antes de entregar.

## Reglas
- No envíes nada al cliente sin aprobación de Javier.
- No inventes datos del cliente: marca las suposiciones como SUPOSICIÓN.
- Señala riesgos (RGPD/protección de datos, alucinaciones, coste por uso) y cómo se mitigan.
