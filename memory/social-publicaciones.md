# Social publicaciones

Contexto
- Orquestacion en n8n, brandbook en Airtable, cerebro en FastAPI (Render).
- Endpoint principal: POST /social/publicar-completo en system-ia-agentes/workers/social/worker.py.

Estado actual
- Se ajusto publicar-completo para leer reglas estrictas desde:
  - "Reglas Estrictas"
  - "Reglas Estrictas (Lo que NO debe hacer)"
- Se debe enviar desde n8n solo cliente_id y datos_marca si se usan credenciales en Supabase.

Payload recomendado n8n (modo Expression)
={{
  "cliente_id": $json["ID Cliente"],
  "datos_marca": $json
}}

Credenciales
- La fuente deseada es Supabase por cliente_id.
- Render mantiene credenciales generales y API keys.

Pendiente
- Confirmar deploy de cambios y probar publicacion.
