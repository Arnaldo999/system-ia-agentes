---
title: Patrón de onboarding — cliente nuevo Arnaldo (brief + propuesta)
tags: [onboarding, ventas, cliente-nuevo, patron-reutilizable, proyecto-arnaldo]
source_count: 1
proyectos_aplicables: [arnaldo]
proyecto: arnaldo
---

# Patrón de onboarding de cliente nuevo (Arnaldo)

## Definición

Flujo estandarizado para convertir un contacto interesado en cliente pago, desde el primer mensaje de WhatsApp hasta el arranque del desarrollo. Implementado por primera vez con [[cesar-posada]] (abril 2026) y planteado como template para próximos clientes.

## Flujo completo

```
CONTACTO INICIAL
  ↓ (Arnaldo conversa por WhatsApp)
ARMAR ENTREGABLES
  ├─ Formulario brief HTML (específico al vertical)
  └─ Propuesta comercial HTML (scope + precios)
  ↓ (deploy a Coolify Hostinger)
ENVIAR POR WHATSAPP
  ├─ Link al formulario
  ├─ Link a la propuesta
  └─ Resumen de precios (USD 300 impl + USD 80/mes)
  ↓ (cliente completa el brief)
RECIBIR BRIEF (.md)
  ↓
COORDINAR PAGO (privado por WhatsApp)
  ↓
CONSTRUIR ECOSISTEMA
  ├─ Base Airtable nueva
  ├─ Worker FastAPI
  ├─ CRM web adaptado
  ├─ Onboarding WhatsApp YCloud
  ├─ Deploy Coolify Hostinger
  └─ Capacitación
  ↓
LANZAMIENTO
```

## Entregables estándar

### 1. Formulario de brief (HTML estático)

**Ubicación**: `01_PROYECTOS/01_ARNALDO_AGENCIA/clientes/{slug-cliente}/brief.html`

**Patrón de 7 secciones** (personalizables según vertical):

| Sección | Qué pide |
|---------|----------|
| 1. Datos del negocio | Nombre comercial, razón social, ubicación, web, redes, horarios |
| 2. Equipo | Dueño + asesores (lista dinámica) + WhatsApp del bot |
| 3. Servicios | Checkboxes multi-select con los servicios típicos del vertical |
| 4. Catálogo | Lista dinámica de items (paquetes / productos / servicios con precio) |
| 5. Proceso de venta | Preguntas frecuentes, criterios cotización, "lead caliente" |
| 6. Tono del bot | Informal/formal, emojis, saludo, fallback |
| 7. Extras | Recordatorios, follow-ups, integraciones opcionales |

**Comportamiento al enviar**:
- Genera un `.md` formateado con todo el brief
- Descarga automática al dispositivo del cliente
- Abre WhatsApp con mensaje corto pre-llenado hacia el número de Arnaldo
- Cliente adjunta manualmente el archivo recién descargado

**Por qué este método**:
- Cero infraestructura server-side (sin webhooks, sin email automatizado, sin endpoint de recepción)
- El cliente no tiene que pensar "a dónde mandarlo"
- Arnaldo lo recibe en WhatsApp donde ya está chateando
- Archivo `.md` es legible nativamente por Claude para análisis posterior

**Validaciones**:
- Campos obligatorios: nombre del negocio, ciudad, dueño, WhatsApp dueño, WhatsApp bot
- Al menos 1 servicio marcado
- Scroll + focus al primer campo faltante si hay error

**Diseño**: Tailwind CDN, paleta profesional del vertical (ej: celeste/verde para turismo, dorado/marrón para estética, etc.), fuente Inter, cards con sombra sutil.

### 2. Propuesta comercial (HTML estático)

**Ubicación**: `01_PROYECTOS/01_ARNALDO_AGENCIA/clientes/{slug-cliente}/propuesta.html`

**Secciones**:
1. Hero con nombre del cliente + fecha
2. "Qué implementamos" — 6 features con íconos
3. Stack técnico transparente (tags)
4. Inversión — 2 tarjetas (pago único + mensualidad)
5. Cronograma visual (timeline 5 hitos)
6. Próximos pasos (3 pasos numerados)
7. CTA — botón WhatsApp con mensaje pre-llenado

**Precios estándar** (actualizar según complejidad si el brief lo exige):
- **Implementación**: USD 300 pago único
- **Mantenimiento**: USD 80/mes

**Info de pago**: NO incluida en el HTML — se coordina por privado tras recibir el brief.

### 3. Deploy a Coolify Hostinger

Montar los 2 HTMLs como static site dentro del backend `system-ia-agentes` ya deployado:

```python
# main.py
from fastapi.staticfiles import StaticFiles
app.mount("/propuestas", StaticFiles(directory="clientes-publicos"))
```

Copiar los archivos a `backends/system-ia-agentes/clientes-publicos/{slug}/` y commit + push.

**URLs resultantes**:
- `https://agentes.arnaldoayalaestratega.cloud/propuestas/{slug}/brief.html`
- `https://agentes.arnaldoayalaestratega.cloud/propuestas/{slug}/propuesta.html`

**Por qué no Vercel**:
- Evita cupo limitado del plan Hobby (100 deploys/día)
- Subdomain propio es más profesional que `.vercel.app`
- No requiere configurar DNS nuevos
- Deploy automático al push del repo existente

### 4. Mensaje WhatsApp para enviar al cliente

Template:

```
Hola [NOMBRE]! 👋

Te paso todo lo que necesitás para que arranquemos con el bot + CRM para tu [VERTICAL].

📋 FORMULARIO (completalo para arrancar)
Son unos 10 minutos. Cuando termines, el mismo formulario te descarga un archivo y abre WhatsApp para que me lo mandes:
👉 https://agentes.arnaldoayalaestratega.cloud/propuestas/{slug}/brief.html

📄 PROPUESTA COMPLETA
Acá ves todo lo que implementamos, el stack técnico, los tiempos y la inversión:
👉 https://agentes.arnaldoayalaestratega.cloud/propuestas/{slug}/propuesta.html

💰 Resumen inversión:
• Implementación única: USD 300
• Mantenimiento mensual: USD 80

⏱ Entrega: 7-10 días hábiles desde que reciba el brief + pago.

Los detalles de pago y cualquier duda me los escribís por acá. 🚀

— Arnaldo
```

## Costos de producir los entregables

**Tiempo Claude + humano**: ~30 min para armar formulario + propuesta personalizados por vertical + deploy.

**Infra adicional**: cero — aprovecha el backend FastAPI existente.

**Reutilización**: el próximo cliente solo necesita ajustes menores (cambiar palabras del vertical, agregar/quitar checkboxes específicos, ajustar precios si el alcance cambia).

## Ventajas del patrón

1. **Profesionalidad**: el cliente ve 2 páginas limpias con dominio propio — impresión de agencia seria
2. **Self-service**: el cliente completa a su ritmo, cuando puede, sin presión
3. **Brief estructurado**: evita ir-y-venir por WhatsApp preguntando cosas. Todo junto en un solo documento
4. **Base para IA**: el `.md` resultante se lee perfecto por Claude para armar bot + CRM exacto
5. **Sin dependencias externas**: no depende de Typeform / Google Forms / Formspree / etc.
6. **Transparencia**: el cliente ve el stack técnico completo + los precios antes de cualquier compromiso

## Limitaciones conocidas

- **Límite WhatsApp 4000 chars**: si el brief es muy largo, el mensaje pre-llenado se trunca. Mitigación: la sección "envío" detecta esto y sugiere adjuntar el archivo en vez del texto crudo.
- **No hay base de datos de leads de prospectos**: si Cesar no avanza, el brief queda en WhatsApp de Arnaldo. No hay pipeline de "prospectos interesados" automatizado.
- **Sin integración de pago**: el link de MercadoPago / pago se comparte por privado manualmente.

Ninguna de estas limitaciones justifica complejidad extra para volumen actual (1-2 clientes nuevos por mes).

## Aplicabilidad

**Aplica a**: cualquier cliente nuevo de Arnaldo para bot + CRM. Probado para [[cesar-posada]] (turismo), plantilla disponible para:
- Restaurantes / gastronomía
- Estéticas / salud / belleza
- Academias / consultoras
- Comercios retail
- Otros verticales con consultas recurrentes por WhatsApp

**NO aplica a**:
- Clientes de [[lovbot-ai]] (stack Robert usa PostgreSQL + Meta + OpenAI propio Robert)
- Clientes de [[system-ia]] (stack Mica usa Easypanel + OpenAI Arnaldo compartido)
- Proyectos enterprise con pricing custom (> USD 1000)

## Fuentes

- [[raw/arnaldo/sesion-2026-04-22-brief-cesar-posada]] — ingesta de la sesión original
- [[wiki/entidades/cesar-posada]] — primer cliente que usó este patrón
- [[wiki/entidades/agencia-arnaldo-ayala]] — dueño del patrón
