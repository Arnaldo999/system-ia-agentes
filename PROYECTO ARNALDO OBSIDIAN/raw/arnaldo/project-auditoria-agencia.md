---
name: Sistema de auditoría de la agencia — estado y roadmap
description: Estado de la Fase 1 de estabilización y plan de Fase 2 del sistema de auditoría
type: project
---

## Estado Fase 1 — Estabilización operativa (2026-04-10)

Implementada. Pendiente activación manual para ser operativa al 100%.

### Completado
- `base_directory` Coolify corregido: `/01_PROYECTOS/01_ARNALDO_AGENCIA/backends/system-ia-agentes`
- Fix alerta Telegram workflow redes Arnaldo (`aJILcfjRoKDFvGWY`): `specifyBody keypair → json`
- Workflow Monitor YCloud Maicol creado en n8n Arnaldo (ID: `5nWay88239sreaj7`) — **INACTIVO**
- Workflow Monitor LinkedIn Mica creado en n8n Mica (ID: `jUBWVBMR6t3iPF7l`) — **INACTIVO**

### Pendiente activación manual (Fase 1 no operativa hasta completar)
1. **Arnaldo** — n8n Arnaldo UI:
   - Credentials → New → HTTP Header Auth
   - Nombre: `YCloud API Key — Maicol` | Header: `X-API-Key` | Valor: `YCLOUD_API_KEY_MAICOL` (desde Coolify)
   - Asignar al nodo `📡 GET YCloud phoneNumbers` del workflow `5nWay88239sreaj7`
   - Activar toggle del workflow
2. **Mica** — n8n Mica UI:
   - Abrir workflow `jUBWVBMR6t3iPF7l`
   - Activar toggle

**How to apply:** Al inicio de sesión, verificar si Arnaldo confirmó estas activaciones. Si no, recordarlo antes de pasar a Fase 2.

---

## Fase 2 — Sistema formal de auditoría (pendiente diseño)

Orden acordado con Arnaldo:
1. **Infraestructura y health** — FastAPI, Coolify, n8n, servicios externos
2. **Workflows y workers** — estado activo/inactivo, últimas ejecuciones, errores
3. **Integraciones y tokens** — YCloud, LinkedIn, Meta, Gemini, Airtable
4. **CRM / tenants** — consistencia Supabase, estado pagos, expiración
5. **Reporte consolidado** — Telegram o dashboard unificado

Opción 2 monitor YCloud (endpoint FastAPI proxy `/clientes/arnaldo/maicol/ycloud-status`) anotada como mejora futura dentro de Fase 2 — no en Fase 1.

**Why:** Arnaldo quiere operación segura y estable antes de sistema de auditoría completo.
**How to apply:** No diseñar Fase 2 hasta confirmar que Fase 1 está 100% operativa.
