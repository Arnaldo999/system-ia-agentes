# Directiva: Onboarding Cliente Nuevo

**Cuándo usar**: Ventas cerró un cliente. Hay un brief en `handoff/`. Hay que implementar todo desde cero.

## Entradas requeridas

| Campo | Descripción |
|-------|-------------|
| `cliente` | Nombre del negocio |
| `proyecto` | arnaldo \| robert (lovbot) \| mica (system-ia) |
| `tipo` | bot_whatsapp \| redes_sociales \| ambos |
| `nicho` | inmobiliaria \| gastronomia \| [otro] |

Leer antes de empezar:
```
handoff/brief-[cliente].md          ← brief de Ventas
memory/infraestructura.md           ← URLs, UUIDs disponibles
memory/nuevo-cliente-redes-sociales.md  ← si tiene redes
```

## Herramientas

| Script | Propósito |
|--------|-----------|
| `execution/create_tenant.py` | Crear tenant en Supabase (CRM SaaS) |
| `execution/deploy_service.py` | Deploy worker en Coolify |
| `execution/coolify_manager.py` | Gestión de env vars en Coolify |

## Flujo — Bot WhatsApp

### Paso 1 — Confirmar proyecto destino
**Preguntar explícitamente**: "¿Este cliente va con Arnaldo / Robert / Mica?"

| Proyecto | Worker base | n8n | Coolify |
|----------|-------------|-----|---------|
| arnaldo | `workers/clientes/arnaldo/` | n8n.arnaldoayalaestratega.cloud | Coolify Hostinger |
| robert  | `workers/clientes/lovbot/`  | n8n.lovbot.ai | Coolify Hetzner |
| mica    | `workers/clientes/system-ia/` | Easypanel Mica | Easypanel Mica |

### Paso 2 — Copiar worker demo
```bash
# NUNCA editar los demos, siempre copiar
cp workers/demos/[nicho]/worker.py \
   workers/clientes/[proyecto]/[cliente]/worker.py
```

### Paso 3 — Adaptar worker
- Nombre del negocio, industria, tono
- Flujo conversacional (menú, zonas, precios, servicios)
- Integrar con Airtable del cliente (base_id, tabla)
- Número bot y número asesor

### Paso 4 — Crear base Airtable

Tablas mínimas:
```
Clientes: Nombre, Teléfono, Score, Fecha, Zona, Presupuesto, Email
[Catálogo]: según nicho (Propiedades / Menú / Servicios)
```

### Paso 5 — Configurar env vars en Coolify
```python
python execution/coolify_manager.py set-env \
  --vps [proyecto] \
  --uuid [UUID_APP] \
  --vars NUMERO_BOT_[CLIENTE]=xxx AIRTABLE_BASE_[CLIENTE]=xxx ...
```

Variables mínimas:
```
YCLOUD_API_KEY (arnaldo) | META_ACCESS_TOKEN (robert/mica)
NUMERO_BOT_[CLIENTE]
NUMERO_ASESOR_[CLIENTE]
AIRTABLE_TOKEN
AIRTABLE_BASE_[CLIENTE]
GEMINI_API_KEY
```

### Paso 6 — Registrar router en main.py
```python
from workers.clientes.[proyecto].[cliente] import worker as [cliente]_worker
app.include_router([cliente]_worker.router)
```

### Paso 7 — Deploy
Seguir `directives/deploy_worker.md`

### Paso 8 — Configurar webhook
- **YCloud** (arnaldo): panel YCloud → webhook URL = `https://agentes.arnaldoayalaestratega.cloud/[cliente]/webhook`
- **Meta** (robert/mica): Meta Developer → webhook = `https://agentes.lovbot.ai/[cliente]/webhook`

### Paso 9 — Test end-to-end
Mandar "hola" al número del bot y verificar flujo completo.

### Paso 10 — CRM SaaS (si aplica)
```bash
python execution/create_tenant.py \
  --slug [cliente] \
  --nombre "[Nombre Negocio]" \
  --proyecto [robert|mica]
```

## Flujo — Redes Sociales

### Paso 1 — Datos requeridos del cliente
- Page ID Facebook
- IG Business Account ID
- Meta App con permisos `pages_read_engagement`, `instagram_manage_comments`

### Paso 2 — Brandbook en Supabase
Ver `memory/nuevo-cliente-redes-sociales.md` para el SQL exacto.

### Paso 3 — Tabla Branding en Airtable
Colores de marca, tono, industria, logo URL, hashtags.

### Paso 4 — Workflow n8n
Crear "Publicar Diario — [Cliente]":
- Schedule → Brandbook Airtable → Gemini → Cloudinary → FB/IG/LinkedIn
- Activar toggle manualmente en n8n UI

### Paso 5 — Test
Ejecutar manualmente el workflow y verificar publicación.

## Documentación final (obligatoria)

- [ ] `memory/infraestructura.md` — agregar endpoint del nuevo servicio
- [ ] `ai.context.json` — agregar cliente en `proyectos`
- [ ] `handoff/brief-[cliente].md` — marcar `status: implementado`
- [ ] Crear `memory/project_[cliente].md` si tiene lógica especial

## Casos límite

- **Sin número de WhatsApp confirmado** → no avanzar con worker
- **Sin acceso Meta Business** → no avanzar con redes
- **Cliente tiene Airtable propio** → adaptar base_id, no crear base nueva
- **Nicho nuevo** (no inmobiliaria/gastro) → crear worker desde cero basado en `_base/`
