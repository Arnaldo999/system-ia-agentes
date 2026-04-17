---
name: monitor-errores
description: Monitoreo proactivo de todas las automatizaciones de System IA. Usá esta skill cuando querés saber el estado de los servicios, cuando algo no funciona, cuando sospechas que hay un error silencioso, o para hacer un chequeo de rutina. Triggers: "chequeá los servicios", "algo falló", "están funcionando las automatizaciones", "monitor", "health check", "status", "/monitor-errores". USAR SIEMPRE antes de debuggear cualquier problema de producción.
---

# /monitor-errores — Monitor de Automatizaciones System IA

Ejecutá este chequeo completo en orden. No te saltes pasos — los errores silenciosos viven en los detalles.

## Stack a monitorear

| Servicio | URL health | Criticidad |
|----------|-----------|------------|
| FastAPI Arnaldo (principal) | `https://agentes.arnaldoayalaestratega.cloud/health` | 🔴 CRÍTICO |
| FastAPI Robert (lovbot) | `https://agentes.lovbot.ai/health` | 🔴 CRÍTICO |
| n8n Arnaldo | `https://n8n.arnaldoayalaestratega.cloud/healthz` | 🔴 CRÍTICO |
| n8n Robert | `https://n8n.lovbot.ai/healthz` | 🟡 IMPORTANTE |
| Worker Maicol (bot WhatsApp) | `https://agentes.arnaldoayalaestratega.cloud/clientes/arnaldo/maicol/health` | 🔴 CRÍTICO — cliente real |
| Worker Social (redes) | `https://agentes.arnaldoayalaestratega.cloud/social/health` | 🟡 IMPORTANTE |

---

## PASO 1 — Health check de todos los servicios FastAPI

Corré estos curl en paralelo:

```bash
echo "=== FastAPI Arnaldo ===" && curl -s --max-time 10 "https://agentes.arnaldoayalaestratega.cloud/health"
echo "=== FastAPI Robert ===" && curl -s --max-time 10 "https://agentes.lovbot.ai/health"
```

**Interpretar respuesta:**
- `{"status":"ok"}` o similar → ✅
- Timeout o connection refused → ❌ CAÍDO
- Respuesta inesperada → ⚠️ REVISAR

---

## PASO 2 — Chequeo n8n via MCP

Consultá las últimas ejecuciones fallidas en ambas instancias n8n.

**Para n8n Arnaldo** (MCP `mcp__n8n`):
- Listar workflows activos: `mcp__n8n__n8n_list_workflows`
- Ver ejecuciones recientes: `mcp__n8n__n8n_executions` con status `error` o `failed`
- Buscar últimas 10 ejecuciones fallidas

**Para n8n Robert** (MCP `mcp__n8n-lovbot`):
- Igual proceso con `mcp__n8n-lovbot__n8n_executions`

**Qué buscar:**
- Workflows que fallaron en las últimas 24hs
- Workflows que dejaron de ejecutarse (scheduled pero sin runs recientes)
- Error messages repetidos (pueden indicar un problema sistémico)

Workflows críticos a verificar en n8n Arnaldo:
- Alertas vencimientos Maicol (Schedule 8am ARG)
- Redes sociales Arnaldo (`aJILcfjRoKDFvGWY`)

---

## PASO 3 — Verificar webhooks activos

```bash
# Webhook YCloud → FastAPI Maicol (simular ping)
curl -s --max-time 10 "https://agentes.arnaldoayalaestratega.cloud/clientes/arnaldo/maicol/whatsapp" \
  -X POST -H "Content-Type: application/json" \
  -d '{"type":"test_ping"}' | head -c 200

# Social webhook Meta
curl -s --max-time 10 "https://agentes.arnaldoayalaestratega.cloud/social/meta-webhook?hub.mode=subscribe&hub.verify_token=systemia_webhook_2026&hub.challenge=MONITOR_CHECK"
```

Respuesta esperada del social webhook: devuelve el challenge. Si no responde → webhook caído.

---

## PASO 4 — Revisar errores capturados por el middleware

El main.py tiene un middleware que captura todos los errores en memoria. Consultarlo siempre:

```bash
# Errores capturados en Arnaldo (últimos 20)
curl -s "https://agentes.arnaldoayalaestratega.cloud/debug/errors?limit=20" | python3 -m json.tool

# Errores en Robert
curl -s "https://agentes.lovbot.ai/debug/errors?limit=20" | python3 -m json.tool
```

Si `total_errores > 0` → revisar cada entry: `endpoint`, `tipo`, `error`, `timestamp`.
Patrones de alerta: mismo error repetido varias veces, errores en `/clientes/arnaldo/maicol/*`.

---

## PASO 5 — Generar reporte de estado

Después de correr todos los checks, generá este reporte exacto:

```
╔══════════════════════════════════════════╗
║     MONITOR SYSTEM IA — [FECHA HORA]     ║
╠══════════════════════════════════════════╣
║ SERVICIOS FASTAPI                        ║
║  [✅/⚠️/❌] FastAPI Arnaldo (principal)  ║
║  [✅/⚠️/❌] FastAPI Robert (lovbot)      ║
╠══════════════════════════════════════════╣
║ N8N WORKFLOWS                            ║
║  [✅/⚠️/❌] n8n Arnaldo — X workflows   ║
║             Fallidos últimas 24hs: X     ║
║  [✅/⚠️/❌] n8n Robert — X workflows    ║
║             Fallidos últimas 24hs: X     ║
╠══════════════════════════════════════════╣
║ WORKERS CRÍTICOS                         ║
║  [✅/⚠️/❌] Bot Maicol (PRODUCCIÓN)     ║
║  [✅/⚠️/❌] Worker Social (redes)       ║
╠══════════════════════════════════════════╣
║ WEBHOOKS                                 ║
║  [✅/⚠️/❌] YCloud → Maicol             ║
║  [✅/⚠️/❌] Meta Social webhook         ║
╠══════════════════════════════════════════╣
║ ESTADO GENERAL: [TODO OK / HAY ERRORES]  ║
╚══════════════════════════════════════════╝
```

---

## PASO 6 — Si hay errores: diagnóstico y fix

Por cada ❌ o ⚠️ encontrado, seguí esta lógica:

### FastAPI caído
- Verificar si es Coolify o el código: `curl coolify.arnaldoayalaestratega.cloud/api/v1/applications/UUID`
- Si el container está corriendo pero la app no responde → restart: POST `/api/v1/applications/UUID/restart`
- Si el container cayó → revisar último deploy, puede ser error de sintaxis Python

### n8n workflow fallido
- Leer el error message del MCP
- Si es credencial expirada (típico en Meta tokens) → avisar a Arnaldo con el workflow específico

### Worker Social caído (redes sociales)
- Este fue el caso de hoy — verificar primero si el token de Meta/Instagram expiró
- Chequear: `curl https://graph.facebook.com/me?access_token=TOKEN`
- Si expiró → proceso de renovación de token largo (avisar a Arnaldo)

- Pingar manualmente: `curl https://system-ia-agentes.onrender.com/health`
- Puede tardar 30-60s en despertar (tier free)
- Verificar que el workflow keep-alive `kjmQdyTGFzMSfzov` esté activo en n8n

---

## PASO 7 — Proponer acción

Siempre terminar con:

```
¿Querés que aplique algún fix ahora?
- [Lista de fixes disponibles con descripción de qué hace cada uno]
- [ ] Reiniciar servicio X en Coolify
- [ ] Revisar token Meta expirado
- [ ] Activar workflow keep-alive en n8n
- [ ] Ver logs completos de X
```

No aplicar fixes automáticamente — siempre pedir confirmación primero.

---

## Programar monitoreo automático

Para correr automáticamente, usar `/schedule` con este comando:
```
/schedule "Correr /monitor-errores y reportar solo si hay errores" cada 1h
```

O crear un workflow en n8n que llame `/monitor-errores` via Claude Code CLI:
```bash
claude -p "Ejecutá /monitor-errores y reportame el resultado" --no-interactive
```
