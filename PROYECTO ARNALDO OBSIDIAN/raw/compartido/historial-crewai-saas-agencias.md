# Registro de Memoria: Desarrollo de Entorno CrewAI y Estructuración SaaS B2B

**Fecha de Registro:** 02 de Marzo de 2026
**Proyecto:** System IA (Agencia de Automatización)
**Stack Tecnológico Principal:** n8n, Coolify, Airtable, CrewAI, Gemini, APIs de Mensajería (WhatsApp/Meta), Webhooks.

Este documento sirve como contexto histórico para cualquier Agente de IA (LLM) que deba continuar trabajando en este proyecto. Resume las configuraciones técnicas y las decisiones de negocio establecidas en esta sesión.

---

## 1. Entorno de Pruebas: CrewAI local con Gemini
Se estableció y probó un entorno de desarrollo seguro para Agentes de IA utilizando **CrewAI**.

*   **Objetivo:** Permitir al Ingeniero (System IA) prototipar, probar y depurar flujos de agentes conversacionales complejos antes de integrarlos a producción en n8n.
*   **Configuración:**
    *   Entorno virtual aislado (`pruebas_crewai/venv`).
    *   Uso de `python-dotenv` para manejo seguro de credenciales (`.env`).
    *   Implementación de **Google Gemini** (específicamente optimizado hacia modelos eficientes como `gemini-2.0-flash-lite`) como LLM cognitivo para los agentes, reduciendo costos durante la etapa de pruebas.
    *   Script base de testeo: `test_basico.py` (ejecutándose exitosamente a nivel terminal).

---

## 2. Desarrollo de Producto: SaaS Gastronómico (Restaurantes y Cafés)
Se pivotó hacia la definición comercial y técnica del producto SaaS que System IA ofrecerá al rubro gastronómico. La estrategia pasó de "vender bots individuales" a "vender una infraestructura de retención por suscripción".

*   **Arquitectura Base:** Single-tenant lógico operado desde un orquestador maestro (n8n en Coolify), utilizando Airtable como base de datos y panel de control del cliente.
*   **Estructura de Tiers (Niveles de Servicio):**
    1.  **BASIC ($47 - $67 USD/mes | Setup: $97 - $147):** Automatización de WhatsApp (Evolution API/WA Baileys), reservas, envío de menú PDF, y confirmación manual de "pago en caja" mediante trigger en chat.
    2.  **PROFESIONAL ($127 - $167 USD/mes | Setup: $297 - $497):** Salto a la **API Oficial de WhatsApp Cloud (Meta)**, Landing Page básica, pasarela de pago (Stripe/MercadoPago) con cobro automático de seña por reserva, y panel en Airtable Interfaces.
    3.  **PREMIUM ($247 - $347 USD/mes | Setup: $597 - $897):** Sistema predictivo de fidelización, invitaciones de cumpleaños automatizadas (con motor n8n), y tableros analíticos en vivo (Looker Studio conectado a Airtable).

*   **Entregables Técnicos/Comerciales Creados:**
    *   `dashboard_presentacion.html`: Panel interactivo para uso interno y reuniones de ventas (presentado a Micaela). Detalla precios de Setup y Mantenimiento.
    *   `PROPUESTAS/Propuesta_Restaurantes_SystemIA.html`: Documento HTML corporativo, imprimible en PDF, diseñado directamente para ser enviado al cliente final gastronómico. Incluye requisitos técnicos preliminares por cada plan.

---

## 3. Modelo B2B: Alianza Estratégica con Agencias de Marketing
Se definió el plan de escalado masivo: vender la infraestructura tecnológica (n8n + IA) a otras agencias de marketing digital que ya poseen clientes de alto valor.

*   **Problema a resolver:** Las agencias de marketing generan "Leads" vía Ads, pero los clientes finales (Bienes Raíces, Clínicas, etc.) tardan en responder y los leads se enfrían.
*   **Solución System IA:** Actuar como el **Middleware Inteligente**. System IA atrapa el lead vía Webhook en milisegundos, un Agente IA (CrewAI/LLM) atiende y califica al lead vía WhatsApp, y finalmente n8n inyecta toda esa data estructurada directamente en el CRM del cliente (cualquiera que utilicen).

*   **Estructura de Alianzas (Tiers B2B):**
    1.  **Partner Estratégico (Co-Branding):** Agencias aliadas mutuamente visibles. Setup $147 / $67 al mes.
    2.  **Marca Blanca (White-Label):** System IA opera invisible desde un subdominio de la Agencia. La agencia cobra el precio que desee al cliente final. Setup $197 / $97 al mes.
    3.  **Infraestructura Dedicada (VPS Mayorista):** Servidor Coolify exclusivo para la Agencia a partir de 10 clientes. $500 despliegue / $350 al mes fijo.

*   **Entregables Técnicos/Comerciales Creados:**
    *   `PROPUESTAS/Propuesta_Agencias_SystemIA.html`: Acuerdo comercial B2B para las agencias socias con los 3 planes descritos.
    *   `dashboard_agencias_b2b.html`: Diagrama y explicación técnica agnóstica de la arquitectura de datos. Describe las "4 Labores" de System IA (Intercepción de Canales, Calificación IA, Sincronización CRM, Exportación a Dashboards de Analítica). Muestra a System IA como los "arquitectos y plomeros de datos".

---

## 🚨 ALERTA CRÍTICA DE INFRAESTRUCTURA: n8n + Easypanel/Coolify (Pérdida de Datos)
⚠️ **EVENTO REGISTRADO:** Pérdida total de flujos y credenciales al actualizar variables de entorno (específicamente la `N8N_ENCRYPTION_KEY`) y hacer re-deploy en Easypanel/Coolify.

**Causa Técnica (Por qué ocurre esto):**
1. **La Trampa de la Encryption Key:** n8n encripta todas las credenciales de la base de datos (contraseñas, tokens de API) usando la variable `N8N_ENCRYPTION_KEY`. Si esta clave se cambia (o se agrega en un deploy posterior) después de haber creado flujos y credenciales iniciales, n8n **no podrá desencriptar la base de datos**. Al no poder leer la DB, puede fallar al arrancar o crear una base de datos nueva/vacía, dando la impresión de que "se borró todo".
2. **Volúmenes No Persistentes (Docker):** Si en Easypanel no se montó correctamente un volumen persistente hacia la ruta interna de n8n (generalmente `/home/node/.n8n`), cada vez que se hace clic en *Deploy*, Docker destruye el contenedor viejo y crea uno nuevo. Todos los datos que no estén en un volumen montado **se eliminan permanentemente**.

**Protocolo de Prevención (Mandatorio para nuevos Deploys):**
*   **PASO 1:** NUNCA modificar la `N8N_ENCRYPTION_KEY` una vez que el servidor tiene flujos de producción. Esta variable debe declararse en el minuto cero de la instalación y nunca más tocarse.
*   **PASO 2:** Asegurar que el volumen de Docker esté firmemente mapeado a `/home/node/.n8n`.
*   **PASO 3:** **Regla de Oro:** Siempre, antes de cualquier reinicio, actualización o cambio de variable en Easypanel/Coolify, se deben exportar manualmente (o vía API) los flujos de n8n en formato JSON y subirlos a un repositorio (Github) como respaldo de emergencia.

---

## 📌 Siguientes Pasos (Para el Agente / Usuario)
1.  **Restauración Inmediata:** Recuperar los flujos borrados utilizando los respaldos JSON previos (JSONs almacenados en la carpeta del repositorio), e insertarlos en la nueva instancia de n8n.
2.  **En Producción:** Trasladar la lógica del agente desarrollado en `pruebas_crewai` a los flujos base de n8n.
3.  **Infraestructura:** Finalizar el armado del "Workspace Maestro" en Airtable que sostendrá a los restaurantes del plan Básico y Profesional.
4.  **Comercial:** Facilitar los HTMLs (`Propuesta_Restaurantes_SystemIA` y `Propuesta_Agencias_SystemIA`) a Micaela para impresión/generación de PDFs y prospección en campo.
