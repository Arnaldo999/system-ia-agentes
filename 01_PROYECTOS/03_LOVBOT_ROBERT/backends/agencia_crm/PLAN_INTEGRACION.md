# Plan de Integracion — Backend CRM Agencia Lovbot

Estado: PROPUESTA — pendiente de aprobacion antes de ejecutar migracion.
Fecha: 2026-04-23

---

## Que hay ahora

- Frontend LIVE en `admin.lovbot.ai/agencia` (Coolify Hetzner).
- El HTML `dev/admin/agencia.html` tiene datos hardcodeados (LEADS_MOCK).
- Hay un banner amarillo en el frontend que dice "MOCKUP — sin backend conectado".
- El boton "+ Nuevo Lead" y los botones Editar/Convertir/Eliminar estan deshabilitados.
- El frontend ya sabe que el backend es `agentes.lovbot.ai/agencia/leads` y la BD `lovbot_agencia_crm`
  (el banner lo cita literalmente; usaremos `lovbot_agencia` como nombre real de la BD).

## BD propuesta

- Nombre: `lovbot_agencia`
- Servidor: VPS Hetzner `lovbot-postgres` (5.161.208.152)
- Usuario Postgres: `lovbot` (mismo usuario que las otras BDs del ecosistema Lovbot)
- Schema: `schema_lovbot_agencia.sql` (este directorio)
- AISLADA de `lovbot_crm_modelo` (esa es la demo inmobiliaria del producto) y de `robert_crm`.

## Tablas del schema

| Tabla | Rol |
|---|---|
| `agencia_fuentes` | Catalogo de canales (landing, fb_ads, referido, etc.) |
| `agencia_leads` | Prospectos en funnel: lead → contactado → propuesta → negociacion → cliente / perdido |
| `agencia_clientes` | Clientes que ya cerraron. FK a lead de origen. Incluye tenant_slug y db_nombre. |
| `agencia_contactos_log` | Historial de interacciones (llamadas, WA, reuniones). Polimorfico: lead o cliente. |
| `agencia_propuestas` | Propuestas formales enviadas. Un lead puede tener varias versiones. |
| `agencia_pagos` | Cobros mensuales de mantenimiento por cliente. Estado: pendiente / pagado / atrasado. |
| `agencia_funnel_resumen` | Vista SQL para las cards del embudo (sin JOIN en el frontend). |

## Variables de entorno necesarias (nuevas o reutilizadas)

Las siguientes vars ya existen para el worker Robert (misma infra Hetzner).
Solo se necesita una variable nueva para apuntar a la BD correcta.

```
# Ya existen — reutilizar
LOVBOT_PG_HOST=<ip o hostname postgres Hetzner>
LOVBOT_PG_PORT=5432
LOVBOT_PG_USER=lovbot
LOVBOT_PG_PASS=<mismo pass>

# Nueva: indica la BD de agencia
LOVBOT_AGENCIA_PG_DB=lovbot_agencia
```

El router FastAPI de agencia se conecta a `lovbot_agencia`, no a `lovbot_crm_modelo`.

## Endpoints FastAPI a crear

Router prefijo: `/agencia`
Archivo: `workers/clientes/lovbot/agencia_crm/router.py`
Se registra en `main.py` como `app.include_router(agencia_router)`.

| Metodo | Path | Descripcion |
|--------|------|-------------|
| GET | `/agencia/funnel` | Conteos por estado (usa vista `agencia_funnel_resumen`) |
| GET | `/agencia/leads` | Lista paginada con filtros: estado, fuente, buscar, responsable |
| POST | `/agencia/leads` | Crear nuevo lead |
| PATCH | `/agencia/leads/{id}` | Actualizar estado, notas, proximo_contacto, etc. |
| DELETE | `/agencia/leads/{id}` | Eliminar lead (soft delete o hard delete — a decidir) |
| POST | `/agencia/leads/{id}/convertir` | Convierte lead en cliente: crea fila en `agencia_clientes` + actualiza estado |
| GET | `/agencia/clientes` | Lista de clientes activos con estado y plan |
| POST | `/agencia/clientes` | Crear cliente directamente (sin pasar por lead) |
| PATCH | `/agencia/clientes/{id}` | Actualizar datos, estado, tenant_slug, etc. |
| POST | `/agencia/contactos-log` | Registrar interaccion (log) sobre lead o cliente |
| GET | `/agencia/contactos-log/{entidad_tipo}/{entidad_id}` | Historial de interacciones de un lead/cliente |
| GET | `/agencia/propuestas` | Lista de propuestas con filtro por lead |
| POST | `/agencia/propuestas` | Crear propuesta |
| PATCH | `/agencia/propuestas/{id}` | Actualizar estado (enviada, aceptada, rechazada, etc.) |
| GET | `/agencia/fuentes` | Lista de fuentes (para poblar selects del frontend) |

## Autenticacion

El frontend ya valida el token `lovbot-admin-2026` en el login screen.
El backend debe verificar el mismo token via header `Authorization: Bearer lovbot-admin-2026`
o query param `token=lovbot-admin-2026` (consistente con el patron del admin actual).

## Cambios al frontend agencia.html

Una vez aprobado el backend, los cambios al frontend son minimos:
1. Reemplazar `LEADS_MOCK` con una llamada `fetch('/agencia/leads')`.
2. Reemplazar `renderFunnelCards()` con `fetch('/agencia/funnel')`.
3. Habilitar botones Editar / Nuevo Lead / Convertir / Eliminar.
4. Agregar modal "Nuevo Lead" con campos: nombre_empresa, nombre_contacto, whatsapp, fuente, estado, notas.
5. Agregar modal "Agregar interaccion" (log de contacto).
6. Agregar filtro "Responsable" en vista Todos los leads.
7. Expandir canales en el select con los valores de `agencia_fuentes`.

Nota: el frontend esta en `demos/INMOBILIARIA/dev/admin/agencia.html` (dev).
NO editar directamente `admin.lovbot.ai` en produccion — iterar en dev y deploy vía Coolify.

## Integracion futura con FB Lead Ads / lead.center

El schema ya tiene:
- `agencia_leads.fb_lead_id` — ID del lead en Facebook Lead Ads
- `agencia_leads.lead_center_id` — ID en lead.center
- `agencia_leads.zapier_data` — payload raw de Zapier

Cuando Robert comparta el flujo lead.center + Zapier, el conector puede hacer
POST a `/agencia/leads` con estos campos adicionales. El schema esta listo.

## Proximos pasos para aprobacion

1. Robert y Arnaldo aprueban este plan y el schema SQL.
2. Ejecutar en Postgres Hetzner: `CREATE DATABASE lovbot_agencia;` + correr el SQL.
3. Agregar var de entorno `LOVBOT_AGENCIA_PG_DB=lovbot_agencia` en Coolify Robert.
4. Crear `workers/clientes/lovbot/agencia_crm/router.py` con los endpoints listados.
5. Registrar el router en `main.py`.
6. Redeploy en Coolify Hetzner (UUID `ywg48w0gswwk0skokow48o8k`).
7. Conectar frontend agencia.html al backend real.
