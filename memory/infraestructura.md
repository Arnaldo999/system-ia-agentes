# Infraestructura y despliegues

Componentes clave
- FastAPI en Render (system-ia-agentes).
- n8n self-hosted para orquestacion.
- Airtable con brandbook por cliente.
- Supabase con credenciales por cliente (cliente_id).

Notas
- Render usa variables de entorno para credenciales generales (Meta, Gemini, Evolution, etc.).
- Webhook Meta: /social/meta-webhook en FastAPI.
