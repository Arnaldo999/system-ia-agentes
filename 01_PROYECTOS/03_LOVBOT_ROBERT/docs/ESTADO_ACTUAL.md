# ESTADO ACTUAL DEL PROYECTO

Proyecto: Lovbot — Robert Bazan
Fecha: 2026-04-10 13:00
Responsable: Claude Sonnet 4.6 / Arnaldo

## Estado
Activo — En desarrollo

## Resumen corto
Alianza comercial Arnaldo + Robert Bazan. Bot WhatsApp inmobiliario live en Coolify Hetzner usando Meta Graph API. CRM SaaS multi-tenant con dev/prod separados. Admin panel live en `admin.lovbot.ai`. n8n en `n8n.lovbot.ai`.

## Entorno
- Producción: ✅ `https://agentes.lovbot.ai`
- CRM Prod: `https://crm.lovbot.ai?tenant=robert`
- CRM Dev: `https://lovbot-demos.vercel.app/dev/crm?tenant=robert`
- Admin: `https://admin.lovbot.ai` — token: `LOVBOT_ADMIN_TOKEN` (env var)
- n8n: `https://n8n.lovbot.ai`
- Repo/backend principal: `01_PROYECTOS/01_ARNALDO_AGENCIA/backends/system-ia-agentes/` (monorepo compartido)
- Workers Robert: `01_PROYECTOS/01_ARNALDO_AGENCIA/backends/system-ia-agentes/workers/clientes/lovbot/`

## Últimos cambios
- Firewall Hetzner configurado hoy: TCP 22, 80, 443 en servidor Lovbot-Projects
- VPS: lovbot-postgres (5.161.208.152) + Lovbot-Projects (5.161.235.99)

## Rutas clave
- `01_PROYECTOS/01_ARNALDO_AGENCIA/backends/system-ia-agentes/workers/clientes/lovbot/`
- `01_PROYECTOS/03_LOVBOT_ROBERT/clientes/`
- Coolify Robert UUID app: `ywg48w0gswwk0skokow48o8k`

## No tocar sin validar
- Workers lovbot en producción
- Supabase tenants `robert` y `demo` — datos reales
- Admin panel `admin.lovbot.ai` — token en env var, no hardcodear
- REGLA: nunca editar CRM prod directo — iterar en dev, copiar a prod con nueva versión

## Pendientes
- Deploy worker Robert + configuración env vars n8n
- Verificar DNS lovbot.ai live post-firewall
- Probar flujo completo bot con Luciano (gastronómico)

## Riesgos
- Coolify Robert accesible en puerto 8000 sin HTTPS (`http://5.161.235.99:8000`) — solo para uso interno
- Credenciales Meta completas en .env pero pendiente verificar webhook Meta apuntando a Coolify

## Próxima acción recomendada
Verificar que webhook Meta apunta a `https://agentes.lovbot.ai/clientes/lovbot/[cliente]/webhook`. Luego configurar env vars en Coolify Robert y hacer deploy del worker.
