---
name: Auto-reparador + Remote Triggers
description: Sistema auto-reparación en Coolify + 3 Remote Triggers en Claude Code cloud
type: project
---

## Auto-Reparador — Integrado en auditor_runner.py (2026-04-12)

**Archivo**: `02_OPERACION_COMPARTIDA/scripts/auto_reparador.py`
**Integración**: Se ejecuta automáticamente desde `auditor_runner.py` cuando hay alertas

### Qué repara automáticamente:
1. **FastAPI Arnaldo caído** → restart Coolify → si falla → deploy completo con force
2. **Evolution instancia desconectada** → restart instancia via API

### Env vars requeridas en Coolify:
- `COOLIFY_URL` = `https://coolify.arnaldoayalaestratega.cloud`
- `COOLIFY_TOKEN` = token API Coolify
- `EVOLUTION_API_URL`, `EVOLUTION_API_KEY` (ya existían)

### Reporte Telegram:
Agrega sección "🔧 AUTO-REPARACIÓN" al reporte con:
- ✅ servicio — acción exitosa
- ❌ servicio — acción fallida, intervención manual

---

## Remote Triggers — Claude Code Cloud (2026-04-12)

**URL**: https://claude.ai/code/scheduled

### Triggers activos:

| Trigger | ID | Schedule | Qué hace |
|---|---|---|---|
| Auditor de Código | `trig_01AJXYSDkvKtmfwfcejNmY3J` | Lunes 10:17 AM ARG | Busca secrets, naming incorrecto, imports rotos, Cal.com v1, prints debug |
| Sync Docs + CLAUDE.md | `trig_01XDfSr6vFwZkNTiapRa1tba` | Miércoles 9:42 AM ARG | Escanea workers vs documentación, actualiza CLAUDE.md si hay cambios |
| Generador de Workers | `trig_01FVyH3ywykvGR51fBKREMht` | Diario 12:33 (PAUSADO) | Lee INSTRUCCIONES_WORKER.md y genera worker clonado con PR |

### Limitaciones Remote Triggers:
- **NO pueden hacer curl a URLs externas** (sandbox bloqueado con proxy)
- SÍ pueden leer/escribir código en el repo GitHub
- SÍ pueden abrir PRs
- Para health checks y restart → usar auto_reparador.py en Coolify (no triggers)

### Para activar Generador de Workers:
1. Crear `INSTRUCCIONES_WORKER.md` en raíz del repo con datos del cliente
2. Activar trigger desde https://claude.ai/code/scheduled
3. Agente genera worker y abre PR
