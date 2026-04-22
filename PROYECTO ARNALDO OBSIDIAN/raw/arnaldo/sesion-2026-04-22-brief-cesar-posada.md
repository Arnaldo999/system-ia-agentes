---
title: Sesión Claude 2026-04-22 — Onboarding cliente nuevo Cesar Posada (turismo)
date: 2026-04-22
type: sesion-claude
proyecto: arnaldo
tags: [proyecto-arnaldo, cliente-nuevo, onboarding, brief, propuesta, agencia-turismo]
---

# Sesión 2026-04-22 — Brief + propuesta Cesar Posada

Se armó el kit de onboarding (formulario de brief + propuesta comercial) para un cliente nuevo de Arnaldo: Cesar Posada, que quiere automatizar su agencia de turismo con bot WhatsApp + CRM.

## Contexto

Cesar contactó a Arnaldo vía WhatsApp queriendo un sistema parecido al que se implementó para [[maicol]] (bot inmobiliario LIVE con Airtable + YCloud + Coolify Hostinger), pero aplicado al rubro turismo.

Antes de empezar a construir, Arnaldo pidió generar:
1. Un formulario para que Cesar complete con todos los datos específicos (nombre agencia, asesores, paquetes, precios, tono del bot)
2. Una propuesta comercial con scope + precio implementación USD 300 + mantenimiento USD 80/mes

## Decisiones tomadas durante la sesión

### Formulario simplificado
- **Formato de envío**: el formulario genera un `.md` descargable + abre WhatsApp con mensaje listo → Cesar adjunta el archivo manualmente. Sin uploads de fotos ni webhooks ni email automático.
- **Destino**: directo al WhatsApp de Arnaldo (`5493765384843`)
- **Motivo**: máxima simplicidad, cero infraestructura server-side para recibir datos, Cesar no tiene que pensar "a dónde mando esto"

### Propuesta comercial
- **Precios**: USD 300 implementación + USD 80/mes mantenimiento
- **Info de pago**: NO incluida en la propuesta — se coordina por privado tras recibir el brief
- **Stack transparente**: se listan todos los servicios que se usan (WhatsApp YCloud, Airtable, Gemini/GPT-4, Coolify, Cal.com, n8n)
- **Cronograma**: 7-10 días hábiles desde pago + brief

### Hosting de los HTMLs
- **No usamos Vercel** — el proyecto del usuario tiene cupo 100 deploys/día agotado por el CRM refactor intenso del día anterior.
- **Alternativa elegida**: servir los archivos desde el backend FastAPI `system-ia-agentes` ya en Coolify Hostinger, bajo ruta `/propuestas/cesar-posada/`.
- **Ventajas**: cero infra nueva, subdomain propio `arnaldoayalaestratega.cloud` (más profesional que un `.vercel.app`), deploys ilimitados.

### Corrección importante del usuario durante la sesión
El usuario aclaró: **"Cesar Posada" es el nombre del contacto, NO asumir que es la marca de la agencia**. La marca la tenemos que preguntar en el formulario. Todos los textos y placeholders corregidos para no prejuzgar.

## Arquitectura de los entregables

### Formulario (brief.html)

7 secciones:
1. **Agencia** — nombre comercial, razón social, ciudad, web, redes sociales, horario
2. **Equipo** — dueño, asesores (lista dinámica con botón "+ Agregar"), WhatsApp del bot
3. **Servicios** — 12 checkboxes (nacionales, internacionales, cruceros, all-inclusive, vuelos sueltos, alojamiento, receptivo, corporativos, luna de miel, familiares, aventura, excursiones) + destinos + temporadas
4. **Paquetes** — lista dinámica con nombre, destino, duración, precio, qué incluye, temporada
5. **Proceso de venta** — preguntas frecuentes, info para cotizar, criterio lead caliente, URL de agenda online
6. **Tono del bot** — formal/informal, emojis, saludo, fallback
7. **Extras** — 6 checkboxes (recordatorio post-viaje, follow-up, recordatorios pago, campañas estacionales, Google Calendar, Mailchimp) + observaciones libres

**Botón principal**: descarga `.md` + abre WhatsApp en secuencia (delay 600ms entre los 2 para que el usuario vea el toast de descarga).

**Validación antes de enviar**: campos obligatorios (nombre comercial, ciudad, dueño, WhatsApp dueño, WhatsApp bot) + al menos 1 servicio marcado.

Diseño: Tailwind CDN, paleta celeste/blanco/verde (profesional turismo), fuente Inter, cards con sombra sutil, radio-buttons con estado visual.

### Propuesta (propuesta.html)

Página única con scroll:
- **Hero**: gradient celeste/índigo con título + meta (fecha, para Cesar Posada, de Arnaldo)
- **Qué implementamos**: 6 features con íconos (bot 24/7, CRM web, paquetes editables, notificaciones, agenda, personalidad propia)
- **Stack técnico**: tags con servicios
- **Inversión**: 2 tarjetas lado a lado — USD 300 pago único (verde) y USD 80/mes (celeste)
- **Cronograma**: timeline visual día por día
- **Próximos pasos**: 3 pasos numerados
- **CTA final**: botón WhatsApp que abre chat con Arnaldo con mensaje pre-llenado "leí la propuesta y quiero arrancar"

## Deploy

**Método elegido**: montar los archivos como static site dentro del backend FastAPI `system-ia-agentes`.

**Proceso** (ejecutado por subagente `deployer`):
1. Creada carpeta `backends/system-ia-agentes/clientes-publicos/cesar-posada/`
2. Copiados los 2 HTMLs a esa ruta
3. Agregado `app.mount("/propuestas", StaticFiles(directory="clientes-publicos"))` en `main.py`
4. Commit + push → Coolify Hostinger redeploy automático
5. Verificado HTTP 200 en ambas URLs

**Commit**: `6231ddd` — feat(propuestas): agregar endpoint /propuestas para servir HTMLs estáticos de clientes

**URLs finales**:
- https://agentes.arnaldoayalaestratega.cloud/propuestas/cesar-posada/brief.html
- https://agentes.arnaldoayalaestratega.cloud/propuestas/cesar-posada/propuesta.html

## Estado al cierre de sesión

✅ Formulario LIVE y probado (29.8 KB)
✅ Propuesta LIVE y probada (15.2 KB)
✅ Mensaje WhatsApp listo y enviado por el usuario a Cesar
⏳ Esperando que Cesar complete el brief y lo envíe por WhatsApp

## Patrón generalizable

Esta sesión generó un **template reutilizable** para onboarding de futuros clientes nuevos de Arnaldo:
- Template formulario brief en `clientes/{cliente-slug}/brief.html` (personalizable por vertical)
- Template propuesta en `clientes/{cliente-slug}/propuesta.html` (stack + precios parametrizables)
- Deploy pattern: `StaticFiles` mount en el backend FastAPI → URL `agentes.arnaldoayalaestratega.cloud/propuestas/{slug}/`

Para próximos clientes (ej: restaurante, estética, consultora): clonar los 2 HTMLs de `cesar-posada/` + adaptar verticales específicos del formulario (paquetes → menú / servicios / especialidades) + ajustar texto de la propuesta si el precio es distinto.

## Próximos pasos (cuando llegue el brief)

Cuando Cesar mande el `.md` completo por WhatsApp:

1. **Ingestar el brief** al proyecto: copiarlo a `01_PROYECTOS/01_ARNALDO_AGENCIA/clientes/cesar-posada/brief-recibido-YYYY-MM-DD.md`
2. **Crear entidades en Obsidian** según lo que diga el brief: agencia (con nombre real), asesores, destinos, etc.
3. **Crear base Airtable** `app{slug_cesar}` con schema para turismo
4. **Scaffold worker**: `workers/clientes/arnaldo/cesar-posada/worker.py` adaptando patrón Maicol
5. **Scaffold CRM**: `demos/turismo/dev/crm-v2.html` como template para nicho turismo
6. **Prompt del bot** específico con lógica de filtrado de leads turísticos
7. **Onboarding WhatsApp oficial** YCloud
8. **Deploy Coolify Hostinger** + smoke tests
9. **Capacitación con Cesar**

## Fuentes

- [[wiki/entidades/cesar-posada]] — entidad cliente
- [[wiki/entidades/agencia-arnaldo-ayala]] — agencia que atiende
- [[wiki/entidades/maicol]] — cliente modelo similar
- [[wiki/entidades/ycloud]] — provider WhatsApp
- [[wiki/entidades/airtable]] — base de datos
- [[wiki/conceptos/matriz-infraestructura]] — stack estándar clientes Arnaldo
