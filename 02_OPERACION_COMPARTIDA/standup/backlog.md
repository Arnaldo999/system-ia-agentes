# Backlog consolidado

**Última actualización**: 2026-04-27 23:59 ART
**Total items abiertos**: 19 (1 🔴 + 4 🟠 + 9 🟡 + 5 🟢)

> Fuente única de verdad para TODOs abiertos del ecosistema. Se actualiza con `/cierre`.

---

## 🔴 Críticos (1)

- [ ] **DMs Messenger Maicol no llegan al webhook real** | proyecto: arnaldo | origen: `memory/ESTADO_ACTUAL.md` | detectado: 2026-04-24
  - Código + simulación funcionan; Meta no dispara webhook real. 5 causas mapeadas en `feedback_meta_dm_webhook_debugging.md`. Próximo paso: screenshot Business Suite Inbox Automations de Maicol.

---

## 🟠 Altos (4)

- [ ] **Maicol conecte IG Business a Page FB** | proyecto: arnaldo | origen: `memory/ESTADO_ACTUAL.md` | detectado: 2026-04-24
  - Link enviado por WhatsApp (`https://www.facebook.com/settings/?tab=linked_instagram`). Esperando acción del cliente. Bloquea IG posts automáticos + bot comentarios IG.

- [ ] **Validación visual CRM v3 Robert + Mica en producción** | proyecto: robert + mica | origen: `memory/ESTADO_ACTUAL.md` | detectado: 2026-04-22
  - Deployado hace 48h+, sin validar. URLs: `crm.lovbot.ai/dev/crm-v2` + `system-ia-agencia.vercel.app/system-ia/dev/crm-v2?tenant=mica-demo`. Probar 3 puertas modal + tab Relaciones + paneles GESTIÓN.

- [ ] **`waba_clients` en seed SQL de `lovbot_crm_modelo`** | proyecto: robert | origen: `feedback_bug_waba_clients_migraciones.md` | detectado: 2026-04-23
  - Deuda técnica que cada cliente nuevo sufre. Workaround manual funciona pero rompe el onboarding automático. Fix: editar seed + smoke test clonando.

- [ ] **Migración Maicol → System User Admin permanente** | proyecto: arnaldo | origen: `memory/ESTADO_ACTUAL.md` | detectado: 2026-04-23 | **deadline: 2026-04-30**
  - Plan programado vía routine remoto `trig_01Xbb6aJwYdQzAB9ZBY5R5yV` para 2026-04-29 09:00 ART. Notificación Telegram al completarse. Ejecución el 30 (día 7 de regla Meta).

---

## 🟡 Medios (9)

- [ ] **Configuración horarios por cliente via env var** | proyecto: compartido | origen: `memory/ESTADO_ACTUAL.md` | detectado: 2026-04-24
  - Hoy `HORARIO_ATENCION` hardcoded por worker. A futuro: env var `INMO_{CLIENTE}_HORARIO` o campo Airtable/Postgres.

- [ ] **Replicar humanización v2 a workers reales clientes** | proyecto: compartido | origen: `memory/ESTADO_ACTUAL.md` | detectado: 2026-04-24
  - Buffer debounce + typing indicator + splitter saludo solo en demos Mica y Robert. Falta propagar a Maicol, Lau y futuros clientes.

- [ ] **Info Robert sobre lead.center + Zapier** | proyecto: robert | origen: `memory/ESTADO_ACTUAL.md` | detectado: 2026-04-23
  - Robert dijo "te explico la próxima semana". Esperando. Slots ya preparados en `agencia_leads` (fb_lead_id, lead_center_id, zapier_data).

- [ ] **Onboarding Cesar Posada (turismo)** | proyecto: arnaldo | origen: `memory/ESTADO_ACTUAL.md` | detectado: 2026-04-22
  - Propuesta enviada, brief pendiente. Cuando devuelva el brief: crear base Airtable turismo + worker en `workers/clientes/arnaldo/cesar-posada/`.

- [ ] **Avisar a Mica — social worker foco inmobiliaria activo** | proyecto: arnaldo | detectado: 2026-04-27
  - Mica no sabe que sus cuentas tienen `SOCIAL_AGENCIA_VERTICAL_FOCO=inmobiliaria` activo. Mensaje listo, falta enviarlo. Incluir instrucciones para desactivar.

- [ ] **CRM Jurídico Mica — SMTP real** | proyecto: mica | detectado: 2026-04-27
  - Emails actualmente son preview HTML. Falta conectar SMTP real para enviar comunicaciones desde el CRM.

- [ ] **CRM Jurídico Mica — Excel Boletín INPI** | proyecto: mica | detectado: 2026-04-27
  - Mica necesita subir Excel del Boletín de Marcas para análisis automático de oposiciones.

- [ ] **CRM Jurídico Mica — Bot WhatsApp captación leads** | proyecto: mica | detectado: 2026-04-27
  - Leads entran manualmente hoy. Necesita bot de captación para automatizar el ingreso.

- [ ] **CRM Jurídico Mica — n8n recordatorios vencimientos INPI** | proyecto: mica | detectado: 2026-04-27
  - Vencimientos de trámites INPI sin alertas automáticas. Necesita workflow n8n con envío email N días antes.

---

## 🟢 Bajos (5)

- [ ] **20 posts educativos pre-cargados Back Urbanizaciones** | proyecto: arnaldo | origen: `memory/ESTADO_ACTUAL.md` | detectado: 2026-04-24
  - Rotación manual vs automática para alimentar el worker social. No urgente, el worker puede generar on-demand.

- [ ] **Rotación de secrets expuestos en screenshots** | proyecto: global | origen: `memory/ESTADO_ACTUAL.md` | detectado: 2026-04-24
  - `LOVBOT_OPENAI_API_KEY`, `OPENAI_API_KEY`, Redis Hetzner password. No urgente pero buena higiene.

- [ ] **Embedded signup Mica: migrar número a Meta Cloud** | proyecto: mica | origen: `memory/ESTADO_ACTUAL.md` | detectado: 2026-04-21
  - Bloqueado por ventana 24-72h de desconexión del número de Evolution. No urgente.

- [ ] **CRM Jurídico Mica — CRUD completo desde UI** | proyecto: mica | detectado: 2026-04-27
  - Editar/eliminar registros aún no conectados a API desde el frontend.

---

## Por proyecto

### Arnaldo (6 items)

1. 🔴 DMs Messenger Maicol no llegan al webhook
2. 🟠 Maicol conectar IG a Page FB
3. 🟠 Migración System User Admin Maicol (deadline 2026-04-30)
4. 🟡 Avisar a Mica foco social inmobiliaria activo
5. 🟡 Onboarding Cesar Posada (esperando brief)
6. 🟢 20 posts educativos Back Urbanizaciones

### Robert (3 items)

1. 🟠 Validación visual CRM v3 (compartida con Mica)
2. 🟠 `waba_clients` en seed SQL modelo
3. 🟡 Info Robert sobre lead.center + Zapier

### Mica (7 items)

1. 🟠 Validación visual CRM v3 (compartida con Robert)
2. 🟡 CRM Jurídico — SMTP real
3. 🟡 CRM Jurídico — Excel Boletín INPI
4. 🟡 CRM Jurídico — Bot WhatsApp captación
5. 🟡 CRM Jurídico — n8n recordatorios vencimientos
6. 🟢 CRM Jurídico — CRUD completo desde UI
7. 🟢 Embedded signup: migrar número a Meta Cloud

### Global / Compartido (3 items)

1. 🟡 Configuración horarios por cliente via env var
2. 🟡 Replicar humanización v2 a workers reales
3. 🟢 Rotación de secrets expuestos

---

## Notas

- **Primer cierre ejecutado 2026-04-24**. El sistema se inicializó con los TODOs que ya vivían en `memory/ESTADO_ACTUAL.md`.
- **Próximo cierre esperado**: 2026-04-25 al terminar el día.
- **Deadline crítico**: 2026-04-30 (migración Maicol System User). Hay routine remoto que dispara 2026-04-29 para prepararlo.
