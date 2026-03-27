# Infraestructura y despliegues

Componentes clave
- FastAPI en Render (system-ia-agentes).
- n8n self-hosted para orquestacion.
- Airtable con brandbook por cliente.
- Supabase con credenciales por cliente (cliente_id).

Notas
- Render usa variables de entorno para credenciales generales (Meta, Gemini, Evolution, etc.).
- Webhook Meta: /social/meta-webhook en FastAPI.

## n8n Producción — Coolify (Hostinger VPS)

- **URL**: https://n8n.arnaldoayalaestratega.cloud
- **API Key**: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJmM2VjOTRiYi1kNjlmLTQ1NjYtYWZkMi1hNDI1OWM0ZTllMDAiLCJpc3MiOiJuOG4iLCJhdWQiOiJwdWJsaWMtYXBpIiwianRpIjoiN2ZiODE5NDQtMmU3Mi00ZjM3LTg3ODgtNTQ3MTA0NjVkYjQzIiwiaWF0IjoxNzc0NjEzNDgxfQ.0Sil51HrgVx6C-TmaHZl1bOQnrYwiqA5cas5C_jPexs
- **Plataforma**: Coolify sobre Hostinger VPS
- **Dominio**: arnaldoayalaestratega.cloud
- **Propósito**: Producción de clientes. Este n8n centraliza todos los VPS futuros.
- **Cliente actual desplegado**: Inmobiliaria Maicol (bot WhatsApp YCloud)
