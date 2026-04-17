---
name: Alianza Robert Bazan (Lovbot)
description: Alianza estrategica con Roberto Lovbot para mercado mexicano — bienes raices y automotriz enterprise
type: project
---

Alianza con **Roberto Lovbot** (alias Robert Bazán) — agencia **Lovbot** (ex "Páginas Rápidas"), 20 años en marketing digital.
- **Contacto**: direccion@lovbot.mx
- **Ubicación**: Vive en Canadá, clientes en México
- **Clientes**: Ford (sureste México), bienes raíces grandes, ex-Hyundai, ex-Volkswagen
- **Su infra**: n8n propio en VPS, Chatwoot, PostgreSQL, filosofía open-source
- **WhatsApp**: Meta Tech Provider directo (WABA propia)

## Productos que Robert quiere lanzar
1. **Agente WhatsApp para vendedores individuales de bienes raíces** — filtra curiosos vs leads maduros
2. **Agente para empresas grandes** — CRM, dashboards, conectividad

Tiene 2 personas trabajando en esto sin cerrar resultados. Busca a Arnaldo como "músculo tecnológico" que ya tiene producto funcionando.

## Acuerdo propuesto
- **Split setup**: 60% Arnaldo / 40% Robert (mínimo aceptable: 55%)
- **Split mantenimiento**: 50/50
- **Revenue share SaaS futuro**: 50/50
- Robert cobra anual al cliente, paga mensual a Arnaldo

## Infraestructura Robert — Hetzner VPS (acceso otorgado 2026-03-30)

| Servicio | URL | Notas |
|---------|-----|-------|
| n8n | https://n8n.lovbot.ai/ | Principal de Robert — MCP conectado |
| Chatwoot | https://chatwoot.lovbot.ai/ | CRM conversacional |
| Coolify (infra Robert) | http://5.161.235.99:8000/ | Proyecto "Lovbot Projects" — n8n activo |
| Coolify (infra Arnaldo en VPS Robert) | http://5.161.208.152:8000/ | Sin proyectos aún — Arnaldo tiene cuenta propia |
| PostgreSQL | http://5.161.208.152:8000/ | VPS Hetzner us-east Ashburn VA |
| Google Drive | Compartido con Arnaldo | Solo si necesario |

- **Servidores Hetzner**: `lovbot-postgres` (CPX11, 5.161.208.152) + `Lovbot-Projects` (CPX21, 5.161.235.99)
- **Acceso**: Arnaldo tiene cuenta propia en ambos Coolify
- **Chatwoot**: Arnaldo tiene usuario `arnaldoayala157@gmail.com`. Labels: `atiende-agenteai`, `atiende-humano`. Canales: Lovbot Marketing (x2).

## Plan estratégico acordado (reunión 2026-03-30)

- **Nicho inicial**: Inmobiliaria — desarrolladores inmobiliarios (tipo agentesinteligentes.mx)
- **VPS actual (Robert)**: Para pruebas, testeos y todo lo de la agencia interna
- **VPS futuro**: Robert comprará VPS dedicado para cada cliente nuevo en producción
- **Separación clara**: infra interna ≠ infra de clientes

## Workflows WhatsApp Coexistence — Tech Provider Meta (creados 2026-04-06)

5 workflows en `n8n.lovbot.ai` basados en el sistema de Kevin (video referencia):

| # | Workflow | ID | Función |
|---|---------|-----|---------|
| 1 | Onboarding Finish | `vF3bMbCzFz3D2W9z` | Recibe IDs (WABA + Phone) del embedded signup |
| 2 | Login Code | `zEyLpnNJeapT9auj` | Intercambia code temporal por token permanente |
| 3 | Suscribir Webhooks | `r7xmihHdyTDYRQyA` | Suscribe mensajes del cliente al webhook Meta |
| 4 | Eventos de mensajes | `OyTCUWbtnigfu5Oh` | GET=handshake + POST=recibe mensajes (acá va el agente IA) |
| 5 | Overrides | `Sc2DO2ernl4MnkqA` | Redirige mensajes de cada cliente a su instancia n8n |

**Todos validados, inactivos. Para activar necesitan:**
- Env vars en n8n: `META_APP_ID`, `META_APP_SECRET`, `META_VERIFY_TOKEN`
- Credenciales HTTP Header Auth para Graph API
- Robert debe proveer los datos de su app Meta Developers

## Arquitectura de flujo por cliente

```
Meta → n8n WF4 → Worker FastAPI → responde via Meta API
                       ↕
                   Chatwoot (chatwoot.lovbot.ai)
                   - Registra conversación
                   - Robert/equipo pueden intervenir
                   - Labels: atiende-agenteai / atiende-humano
```

**Dos modalidades de cliente:**
- **Cliente chico** (VPS compartida): WF4 rutea por `phone_number_id` → Worker FastAPI → Chatwoot bridge
- **Cliente grande** (VPS dedicada): WF5 Override → su propia instancia n8n + Chatwoot propio o canal dedicado

**Chatwoot es obligatorio para TODOS los clientes de Robert** — es el CRM donde el equipo humano ve y puede intervenir las conversaciones.

## Credenciales Meta Tech Provider (guardadas en .env — NO exponer)

| Variable | Notas |
|----------|-------|
| `LOVBOT_META_APP_ID` | App "APP WorkFlow Whats Lovbot V2" |
| `LOVBOT_META_APP_SECRET` | en .env |
| `LOVBOT_META_PHONE_NUMBER_ID` | LOVBOT Marketing Production |
| `LOVBOT_META_WABA_ID` | WABA del Tech Provider |
| `LOVBOT_META_ACCESS_TOKEN` | Token permanente System User "Proveedor-Meta" |
| `LOVBOT_META_VERIFY_TOKEN` | `lovbot_webhook_2026` |

## Coolify Robert (acceso API verificado 2026-04-06)

| Variable | Notas |
|----------|-------|
| `COOLIFY_ROBERT_URL` | `https://coolify.lovbot.ai` (DNS configurado) |
| `COOLIFY_ROBERT_TOKEN` | en .env |
| `COOLIFY_ROBERT_PROJECT_UUID` | Proyecto "Agentes" en Coolify |

- DNS configurado en cPanel lovbot.ai: `coolify.lovbot.ai` + `agentes.lovbot.ai` → `5.161.235.99`
- GitHub App conectada: `agentes-lovbot` → repo `Arnaldo999/system-ia-agentes`

## Workers Demo — Arquitectura definitiva

- **2 workers maestros** en `workers/demos/`: `inmobiliaria/worker.py` + `gastronomia/worker.py`
- Solo para Demos — se potencian continuamente
- Cliente nuevo → copiar worker demo + adaptar → `workers/clientes/lovbot/[cliente]/worker.py`
- **NUNCA editar workers demo directamente**

## Estado (actualizado 2026-04-08)
- **Bot Robert LIVE** en Coolify Robert (`agentes.lovbot.ai`)
  - Menú subnichos al inicio (agencia/agente/desarrolladora)
  - Flujo: subnicho → nombre → email → ciudad → objetivo → tipo → zona → presupuesto → urgencia
  - Desarrolladora tiene preguntas propias (preventa, lotes, inversión)
  - Cal.com integrado con confirmación antes de reservar
  - Días en español, slots UTC-6 (México)
  - Guarda subniche en Airtable campo `Sub_nicho`
- **CRM SaaS LIVE** — separación dev/prod
  - Producción: `crm.lovbot.ai?tenant=robert` (dominio custom, CNAME en cPanel)
  - Desarrollo: `lovbot-demos.vercel.app/dev/crm?tenant=robert`
  - Sistema de versionado con banner "Nueva versión disponible"
  - Login con PIN (SHA-256) validado contra Supabase
  - Validación automática `estado_pago` por `fecha_vence` (sin cron)
  - Pantallas bloqueo: vencido (⚠️ renovar) / suspendido (🔒 contactar soporte)
  - Mi Agenda sincronizada con Airtable (citas reales del bot)
- **Admin panel** — `lovbot-demos.vercel.app/dev/admin` (futuro: `admin.lovbot.ai`)
  - Login con token admin (`LOVBOT_ADMIN_TOKEN` en env)
  - Sidebar: Dashboard + Clientes CRM (+ placeholders para Automatizaciones, Redes, Facturación)
  - Tabla clientes con búsqueda, stats (al_dia/vencido/suspendido/trial)
  - Botones: Renovar (+30d), Suspender, Reactivar, link al CRM
  - Crear nuevo cliente con PIN desde el panel
  - Todo sincronizado con Supabase `tenants`
- **Supabase tenants** — campos agregados: estado_pago, fecha_alta, fecha_vence, email_admin, telefono_admin, monto_mensual, moneda_pago, notas
- **PRÓXIMO PASO**:
  1. Worker genérico que lea airtable_base_id de Supabase por tenant (multi-tenant dinámico)
  2. Configurar `admin.lovbot.ai` en cPanel (CNAME como crm.lovbot.ai)
  3. Env vars Cal.com en Coolify Robert (ya cargadas INMO_DEMO_CAL_API_KEY + CAL_EVENT_ID)

## Carpeta del proyecto
`PROYECTO AGENCIA ROBERT-ARNALDO AYALA/` — brief, contexto completo, presentación HTML, guía Tech Provider

## Red flags (revisadas post-reunión)
- 2 técnicos previos sin cerrar → superado con nuevo acuerdo claro
- VPS dedicado por cliente → arquitectura correcta para escalar

**Why:** Expansión al mercado mexicano enterprise con infra real de Robert.
**How to apply:** Workflows Tech Provider ya en n8n.lovbot.ai. Usar VPS actual para staging/agencia. Cliente nuevo → VPS dedicado Robert.
