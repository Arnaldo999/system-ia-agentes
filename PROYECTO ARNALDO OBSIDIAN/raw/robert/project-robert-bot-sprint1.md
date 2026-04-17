---
name: Robert Bot Sprint 1 — BANT + Conversacional
description: Sprint 1 del bot Robert/Lovbot con BANT, presentación 1-prop-a-la-vez sin menús, anti-friction determinista. Completado 2026-04-16.
type: project
originSessionId: ff264427-3f05-4e1a-a9c9-a3061566ef37
---
# Sprint 1 — Bot Robert Inmobiliaria — COMPLETADO 2026-04-16

Bot WhatsApp profesional para Robert Bazán (Lovbot), desarrollador inmobiliario Misiones Argentina. Meta Graph API + FastAPI + Coolify Hetzner.

## Implementado

### Metodología BANT
- System prompt maneja Caso A (lead desde anuncio con referral) y Caso B (genérico)
- Extrae: Budget, Authority (decide solo/pareja/familia), Need (tipo+zona+objetivo), Timeline
- Datos adicionales: FORMA_PAGO, MOTIVO, SCORE (caliente/tibio/frío)
- Subnicho hardcodeado como "desarrollador inmobiliario" (vende sus propios lotes/desarrollos)

### Parser Meta Graph API completo
- GET `/whatsapp` handshake verificación
- POST parser: text, button, interactive, audio (Whisper), image
- Extracción referral (Click-to-WhatsApp Ads): headline, body, source_url
- Extracción contacts.profile.name (pre-carga nombre)
- Deduplicación por msg_id con set + lock

### Presentación conversacional (NO menús numéricos)
- `_presentar_prop_breve()` — UNA prop a la vez con anchor question
- Step `"explorando"` navegación por keywords deterministas:
  - `_KEYWORDS_SIGUIENTE`: "otra", "siguiente", "no me interesa", "más"
  - `_KEYWORDS_INTERES`: "me interesa", "cuánto sale", "quiero info"
- Step `"ficha"` con detalle completo (solo si lead escribe "me interesa")
- Sin footer `*0* *1* *#*` — lead debe escribir para avanzar

### Anti-friction determinista
- Keywords `_KEYWORDS_PEDIR_OPCIONES` ("que opciones", "que tienen", "bolsillo")
- Detecta ANTES del LLM — muestra 3 props inmediatamente sin pedir presupuesto
- Handler `accion == "mostrar_props"` implementado en Python (antes faltaba)

### Orden correcto en `_procesar()`
Step handlers PRE-LLM → NÚCLEO LLM → Parser → ACCION:
1. Bot pausado check
2. Step `agendar_slots` (deterministic)
3. Step `confirmar_cita` (deterministic)
4. **Step `explorando` (deterministic, movido ANTES del LLM para no depender de su respuesta)**
5. Anti-friction `_pide_opciones_directo` (deterministic)
6. LLM call
7. Parser tolerante
8. Ejecutar ACCION

### Admin endpoints
- POST `/admin/reset-sesion/{tel}` — borra RAM + DB
- POST `/admin/simular-lead-anuncio/{tel}` — simula Caso A sin Meta real
- GET `/admin/ver-sesion/{tel}` — inspecciona estado RAM (para testing)

## Bugs resueltos en Sprint 1 — Sesión 2026-04-16 (test+fix con skill)

**Bug #1**: Bot duplicaba mensajes Bot en historial
- Causa: `_enviar_texto()` ya llama internamente a `_agregar_historial()` (línea 391). Las llamadas extra `_agregar_historial(telefono, "Bot", mensaje_final)` después de `_enviar_texto()` lo duplicaban.
- Síntoma: el LLM en próxima vuelta veía "Bot: X / Bot: X" → confundido, devolvía "problema técnico"
- Fix: removidas las 6 llamadas redundantes (commit `a11201d`)

**Bug #2**: LLM fallaba en mensaje 2+ ("problema técnico")
- Causa: consecuencia de Bug #1 (historial duplicado contaminaba el system prompt)
- Resuelto al fixear Bug #1

**Bug #3**: Step queda en `?` cuando no entró a un step handler
- Causa: cosmético — `sesion.get("step", "inicio")` lo trata como "inicio" internamente
- No requiere fix

**Bug #4**: `resp_presupuesto` se llenaba con texto basura
- Causa: regex `["50", "100", "200", "presupuesto", "precio", "cuánto"]` matcheaba preguntas del cliente como "qué precio?" → guardaba la pregunta como presupuesto
- Fix: regex requiere número + unidad (`\d{1,4}\s*(k|mil|usd|ars|pesos|\$)`) (commit `5dbb8c6`)

**Audio (recepción)**: faltaba en webhook del worker
- Causa: el handler `audio` solo estaba en el webhook genérico `/meta/webhook` de main.py, no en `/clientes/lovbot/inmobiliaria/whatsapp`
- Fix: copiada `_transcribir_audio_meta()` al worker + handler `elif msg_type == "audio"` (commit `b23e357`)

## Bugs resueltos en Caso B — Sesión 2 (test+fix con skill)

**Bug #5**: Bot ofrecía "alquilar" en saludo inicial
- Causa: prompt decía "vivir, invertir o alquilar" pero Robert es desarrollador (NO alquila)
- Fix: cambiado a "vivir o invertir" (commit `6c83494`)

**Bug #6**: `_normalizar_tipo`/`_normalizar_zona` no detectaban dentro de oraciones
- Causa: solo hacían match exacto en diccionario. "busco un lote en San Ignacio" no matcheaba
- Fix: regex `\b{kw}\b` para tipo + búsqueda sin tildes para zonas (commit `019b038`)

**Bug #7**: Cliente que pedía "hablar con asesor humano" era ignorado
- Causa: solo el comando `#` escalaba; el LLM no detectaba la intención natural
- Fix: handler determinista pre-LLM con keywords ("hablar con asesor", "persona real", etc.)
  igual que Bug #1 lección — no confiar en el LLM para reglas críticas (commit `6c83494`)

## Cambio importante: gpt-5-mini → gpt-4o-mini (commit `5a38495`)

`gpt-5-mini` consistentemente >30s con prompt BANT largo → timeouts.
`gpt-4o-mini` ~2-5s, más estable. Fallback Gemini 2.0-flash → 2.5-flash.

## Bugs resueltos antes de Sprint 1 (anteriores)

1. **Webhook Meta apuntaba a UUID n8n inexistente** — fix: URL correcta `/clientes/lovbot/inmobiliaria/whatsapp`
2. **Falta GET endpoint** para handshake Meta — fix: agregado
3. **Bot preguntaba subnicho innecesariamente** (era desarrollador) — fix: hardcoded
4. **Bot ofrecía "alquilar" para lotes** — fix: regla en prompt
5. **EXTRACCIÓN DE DATOS leaks al cliente** (bullets) — fix: parser tolerante regex
6. **ESTADO_REVERSE CRM desalineado** con ESTADOS_VALIDOS backend — fix: aligneado
7. **Anti-friction no funcionaba** (LLM ignoraba excepción en prompt largo) — fix: keywords Python
8. **ACCION mostrar_props declarada pero sin handler** — fix: implementado
9. **Step handlers DESPUÉS del LLM** → si LLM fallaba, no navegaba — fix: movidos ANTES
10. **Menú numérico tipo catálogo** (Robert pidió cambiar) — fix: `_presentar_prop_breve()` + step `explorando`

## Configuración actual

- Backend: `agentes.lovbot.ai` (Coolify Hetzner)
- Coolify App UUID: `ywg48w0gswwk0skokow48o8k`
- Webhook: `https://agentes.lovbot.ai/clientes/lovbot/inmobiliaria/whatsapp`
- Worker: `workers/clientes/lovbot/robert_inmobiliaria/worker.py`
- Número bot Robert: configurar en Meta Business (phone_number_id env)
- LLM: `gpt-5-mini` (OpenAI) principal, `gemini-2.5-flash` fallback
- Database: PostgreSQL `robert_crm` (NO `lovbot_crm`)

## Test cycle validado

Ciclo completo funciona:
```
que opciones tienen → muestra prop 1 con imagen
no me interesa mostrá otra → avanza a prop 2
esta me gusta cuánto sale? → ficha completa con precio/zona/m2
```

Step transitions: `inicio → explorando (idx 0) → explorando (idx 1) → ficha`.

## Pendientes Sprint 2+

- **Probar desde WhatsApp real** (solo probado con curl hasta ahora)
- **Sprint 2**: branching logic caliente/tibio/frío auto-routing
  - Caliente → agendar cita inmediata
  - Tibio → mostrar props + nurturing 3 días
  - Frío → derivar al sitio web + nurturing semanal
- **Sprint 3**: secuencia de 6 follow-ups automáticos
- **Sprint 4**: nurturing long-term (mensual)
- **Sprint 5**: dashboard métricas conversaciones

## Commits del Sprint 1

```
401158e feat(skills): whatsapp-conversational-bot multi-provider
79aa0ae fix(robert-bot): mover step explorando ANTES del LLM call
2a253fa feat(robert-bot): presentación conversacional una a la vez
9056298 fix(robert-bot): anti-friction determinista
fdb4365 feat(robert-bot): add /admin/ver-sesion endpoint
6946559 (anterior) — anti-friction rule en prompt (no funcionaba sola)
```
