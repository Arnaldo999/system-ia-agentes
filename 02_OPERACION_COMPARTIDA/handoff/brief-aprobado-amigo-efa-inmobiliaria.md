# BRIEF TÉCNICO APROBADO: System IA 

**Cliente:** Amigo La EFA (Agencia Inmobiliaria)
**Stakeholder Principal:** Dueño (Amigo de Arnaldo)
**Fecha de Handoff:** 22 de Marzo de 2026

## 1. Problema de Negocio y Cuantificación
*   **Dolor Principal:** El dueño invierte en pautas de Meta (Facebook/Instagram Ads) pero su tiempo (y el de su equipo) es consumido respondiendo a "curiosos" que no tienen intención de compra o alquiler real.
*   **Impacto / Pérdida:** Cuello de botella en la atención. El tiempo perdido respondiendo consultas no calificadas le impide aumentar la inversión publicitaria.
*   **Objetivo de Negocio:** Automatizar la atención inicial, filtrar prospectos basura y que al humano *solo* le lleguen clientes reales/calificados para cerrar. Al ahorrar tiempo, escalarán la inversión publicitaria.

## 2. Alcance Técnico Requerido (El "Qué", no el "Cómo")
La automatización debe contemplar el siguiente recorrido:

1.  **Origen de Datos:** Comentarios y/o Mensajes Directos originados por pautas comerciales en **Meta Ads (Facebook e Instagram)**.
2.  **Atención Contextual:** El sistema (Bot) debe ser capaz de identificar desde **qué anuncio específico** viene el cliente y responderle de manera automatizada y congruente con ESA propiedad anunciada (no con respuestas genéricas).
3.  **Filtrado Inteligente:** El asistente realizará preguntas de pre-calificación (presupuesto, intenciones, tipo de inmueble) para categorizar al prospecto.
4.  **Entrega Final:** Los prospectos marcados como "Interesados calificados" serán derivados a la atención humana (y/o al CRM Inmobiliario construido en la propuesta).
5.  **Exclusiones:** El bot NO cerrará la venta final, ni negociará precios. Solo entrega leads calificados.

## 3. Integraciones Específicas
*   **Meta Graph API:** (Facebook Messenger, Instagram DM).
*   **Disparador:** Webhook de n8n / Meta Ads Lead trigger.
*   **Asistente IA:** Integración con API de LLM (Claude/Gemini/OpenAI) entrenado con contexto inmobiliario.
*   **CRM/Base de datos:** [A conectar con la planilla o app_inmobiliaria].

## 4. Presupuesto y Deadline
*   **Presupuesto Acordado:** [A DEFINIR CON EL CLIENTE / ARNALDO].
*   **Deadline Prometido:** [A DEFINIR ENTRE VENTAS Y DEV].

---
*Nota del Especialista Comercial (Micaela/Ventas):* Arnaldo, este prospecto está súper caliente. Logró entender exactamente nuestra Propuesta de Valor. Su frase *"puedo hacer más publicidad y ahorro tiempo"* significa que entendió el ROI de la agencia. Listo para que Dev empiece a engranar Meta Ads con n8n.
