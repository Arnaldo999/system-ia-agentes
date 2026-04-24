---
name: Playbook — Social Automation Meta (FB+IG posts + comentarios + DMs)
description: Activar publicación automática diaria FB+IG + bot de respuesta a comentarios + bot DMs para un cliente nuevo. Aplica principalmente a Arnaldo (Maicol) y extensible a Mica/Robert. Evita las 6+ horas de debugging del caso Maicol.
type: playbook
proyecto: compartido
tags: [meta, facebook, instagram, social-media, bot-comentarios, playbook]
version: 1
ultima_actualizacion: 2026-04-24
casos_aplicados: [maicol-back-urbanizaciones, arnaldo-agencia]
caso_origen: runbook-meta-social-automation.md
---

# Playbook — Social Automation Meta (FB+IG)

> **Cuándo usar**: cliente pide publicación automática diaria en Facebook + Instagram + bot que responde comentarios/DMs.
>
> **Tiempo esperado siguiendo el playbook**: 30 min. **Tiempo sin playbook**: 6+ horas (caso Maicol original).

## Status del sistema

| Componente | Estado | Casos probados |
|------------|--------|----------------|
| Publicación auto FB | ✅ Maduro | Arnaldo, Maicol |
| Publicación auto IG | ✅ Maduro | Arnaldo, Maicol (pendiente link) |
| Bot comentarios FB | ✅ Maduro | Arnaldo, Maicol |
| Bot comentarios IG | ✅ Maduro | Arnaldo |
| Bot DMs Messenger | 🟡 Deployado, validación real pendiente | Maicol (DMs no llegan al webhook aún) |

## Arquitectura en 1 párrafo

**Una sola app Meta Developer** (`Social Media Automator AI`, App ID `895855323149729`) se comparte con cada BM cliente. **Supabase `clientes`** guarda credenciales por cliente (multi-tenant). **Airtable del cliente** guarda el brandbook. **Backend FastAPI** orquesta: Gemini genera copy + imagen, Cloudinary hostea, Graph API publica. **n8n** dispara diariamente via cron.

## ⚠️ Este playbook remite al runbook detallado

Toda la implementación paso a paso ya vive en:

**`wiki/conceptos/runbook-meta-social-automation.md`** — 690 líneas, 8 gotchas documentados, casos de falla reales.

Este playbook **no duplica** ese runbook, solo lo referencia y agrega la capa de patrón reutilizable.

---

## Los 8 gotchas conocidos (resumen)

| # | Gotcha | Cuándo aparece |
|---|--------|----------------|
| 1 | User Token ≠ Page Access Token | Al generar token inicial |
| 2 | System User Admin requiere 7 días antigüedad | Al intentar atajo permanente |
| 3 | IG debe estar conectado a Page FB explícitamente | Post FB OK pero IG error 10 |
| 4 | Page Token hereda estado de sesión FB del navegador | Token "permanente" muere en 6h |
| 5 | Token debe ir en `meta_access_token`, NO en `token_notas` | Bug silencioso, muy difícil de detectar |
| 6 | Messenger requiere primer mensaje del usuario (24h window) | DMs en frío imposibles |
| 7 | Messenger Send API usa `messaging_type: "RESPONSE"` | Tipo incorrecto rechaza envío |
| 8 | Agente NO debe escribir tokens via bash curl con vars shell | Strings largos con caracteres especiales se pierden |

**Detalles completos, causas raíz y fixes**: ver runbook.

---

## Pre-check antes de arrancar onboarding

Si alguna de estas cosas NO está, el playbook se va a trabar. Resolver antes:

- [ ] Cliente ya tiene BM de Meta Business creado
- [ ] Página FB + IG Business del cliente conectados al BM del cliente
- [ ] **IG Business está LINKEADO a la Page FB** (no solo "en el mismo BM") — link: `https://www.facebook.com/settings/?tab=linked_instagram`
- [ ] Tú (Arnaldo) agregado al BM cliente como Administrador
- [ ] Base Airtable del cliente creada con tabla `Branding` populada (ver playbook #5 `airtable-schema-setup`)
- [ ] Supabase `clientes` accesible (tabla multi-tenant)
- [ ] Backend FastAPI `agentes.arnaldoayalaestratega.cloud` corriendo y healthy

## Flujo resumido (referir a runbook para detalles)

```
1. Obtener FB Page ID + IG Account ID (3 min)
   └─ business.facebook.com → BM cliente → Páginas/IG → "Identificador"

2. Compartir app `Social Media Automator AI` con BM cliente (3 min)
   └─ Permisos: Desarrollar, Ver estadísticas, Probar (NO Administrar)

3. Cliente acepta la app en su BM (1 min)

4. Generar Page Access Token permanente (5 min) ⚠️ Gotcha #1, #4
   ├─ Graph API Explorer → User Token con 10-11 scopes
   ├─ Extender a 60 días (long-lived)
   ├─ Intercambiar: <page_id>?fields=access_token
   ├─ Verificar Expires: Never (Debug Token)
   └─ SESIÓN FRESCA FB + todo en 1 tab sin pausas

5. UPDATE Supabase `clientes` con SQL Editor (2 min) ⚠️ Gotcha #5, #8
   └─ SIEMPRE vía SQL Editor, NO Table Editor ni curl

6. Duplicar workflow n8n (5 min)
   ├─ Base: `aJILcfjRoKDFvGWY` (Arnaldo)
   ├─ Cambiar URL Airtable al base del cliente
   └─ Ajustar schedule para evitar hora pico

7. Test E2E (3 min)
   └─ curl al endpoint con brandbook del cliente
   └─ Verificar "instagram.success" + "facebook.success"

8. Activar bot comentarios (Fase 2) — opcional
   ├─ Webhook app ya configurado
   ├─ Suscribir Page: POST /<page_id>/subscribed_apps
   └─ Suscribir IG: POST /<ig_id>/subscribed_apps

9. Activar bot DMs (Fase 3) — opcional ⚠️ DMs Maicol pendientes
   ├─ Agregar scope `pages_messaging`
   ├─ Regenerar token con nuevo scope
   └─ Re-suscribir Page con field `messages`

10. Día 8+ — Migrar a System User permanente (robusto)
```

## Si algo falla — primer diagnóstico (5 min)

| Síntoma | Causa | Referencia |
|---------|-------|------------|
| `code 190` "Invalid JSON for postcard" | User Token, no Page Token | Gotcha #1 |
| `code 190 subcode 463` "Session expired" | Page Token heredó sesión vieja | Gotcha #4 |
| `code 10` "no permission" | IG no linkeado a Page | Gotcha #3 |
| DMs no llegan al webhook | Config subscribe / opt-in / propagación | `feedback_meta_dm_webhook_debugging.md` |

---

## Debt específica abierta

- **Maicol DMs Messenger** — Código deployado 2026-04-24 (commit `675dc9e`) pero DMs reales no llegan al webhook. 6 causas posibles a verificar (ver `feedback_meta_dm_webhook_debugging.md`). Siguiente sesión con Maicol retomar.
- **Migración System User Admin Maicol** — programada 2026-04-30 (día 7 desde onboarding).

---

## Checklist final

- [ ] Page Access Token: Expires = Never (verificado en Debug Tool)
- [ ] Registro Supabase `clientes` con columna correcta (`meta_access_token`)
- [ ] Workflow n8n activo y con schedule OK
- [ ] Test endpoint: IG success + FB success
- [ ] Brandbook Airtable completo (Industria, Servicio, Tono, Logo, Colores, CTA, Page ID, IG ID)
- [ ] (Fase 2) Page + IG suscritas al webhook
- [ ] (Fase 3) Scope `pages_messaging` agregado si querés DMs

---

## Archivos que tocás

```
backends/system-ia-agentes/workers/social/worker.py     ← código (1900+ líneas, NO reescribir)
Supabase tabla `clientes` (proyecto ArnaldoAyalaAgencia) ← INSERT / UPDATE
Airtable del cliente, tabla `Branding`                   ← populate
n8n workflow `aJILcfjRoKDFvGWY` (base Arnaldo)          ← duplicar
developers.facebook.com/apps/895855323149729/           ← Meta app config
```

---

## Decisiones arquitectónicas (por qué así)

- **Una sola app Meta compartida**: simplifica review de Meta, permisos, secrets. Cada cliente aislado por su propio token.
- **Supabase y no env vars**: multi-tenant real (N clientes sin redeploy).
- **Airtable para brandbook y no Supabase**: el cliente o el equipo editan branding. Supabase es solo creds.
- **Page Token y no System User desde día 1**: Meta bloquea admins nuevos de BM por 7 días.

---

## Histórico de descubrimientos

- **2026-04-07** — Workflow base Arnaldo creado (`aJILcfjRoKDFvGWY`).
- **2026-04-23** — Primer onboarding cliente (Maicol). 6+ horas de debugging. Descubiertos gotchas #1, #2, #3. Publicación FB LIVE.
- **2026-04-24** — Gotchas #4 (sesión FB), #5 (columna Supabase), #6-#8 (DMs + bash vars). DMs deployados pero no validados.
- **Pendiente 2026-04-30** — Maicol día 7 en BM: migrar a System User permanente.

---

## Referencias cruzadas

- `wiki/conceptos/runbook-meta-social-automation.md` — implementación detallada 690 líneas
- `feedback_meta_dm_webhook_debugging.md` — checklist DMs pendiente Maicol
- `wiki/conceptos/meta-graph-api.md` — referencia general de la API
- `wiki/conceptos/meta-webhooks-compliance.md` — compliance Meta
- `wiki/conceptos/meta-business-portfolio-verificacion.md` — verificación BM
- `wiki/conceptos/meta-tech-provider-onboarding.md` — TP onboarding (caso Robert)
