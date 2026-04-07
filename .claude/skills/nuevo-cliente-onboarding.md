---
name: nuevo-cliente-onboarding
description: Proceso completo de onboarding para un nuevo cliente de System IA. Activar cuando el pedido sea "nuevo cliente", "onboarding de [nombre]", "arrancá con [cliente]", "tenemos un cliente nuevo", "configurá todo para [negocio]", "armá el sistema para [cliente]", o cuando Ventas haya cerrado un cliente y haya que implementar. Lee memory/nuevo-cliente-redes-sociales.md y memory/infraestructura.md antes de empezar.
---

# SKILL: Nuevo Cliente — Onboarding Completo

## Paso 0: Leer antes de hacer CUALQUIER cosa

```
memory/nuevo-cliente-redes-sociales.md  ← proceso completo documentado
memory/infraestructura.md               ← URLs, UUIDs, instancias disponibles
handoff/brief-[cliente].md              ← brief de Ventas (si existe)
```

**Regla crítica**: SIEMPRE confirmar "¿esto va al proyecto de Arnaldo / Robert / Mica?" antes de operar con cualquier API externa.

## Checklist de onboarding por tipo de proyecto

### Bot WhatsApp

- [ ] **Brief recibido** desde Ventas en `handoff/brief-[cliente].md`
- [ ] **Determinar API**: YCloud (Arnaldo/Maicol) o Meta Graph API (Robert/lovbot)
- [ ] **Número de WhatsApp** confirmado con el cliente
- [ ] **Copiar worker demo** correspondiente:
  - Inmobiliaria: `workers/demos/inmobiliaria/worker.py` → `workers/clientes/[proyecto]/[cliente]/worker.py`
  - Gastronómico: `workers/demos/gastronomia/worker.py` → idem
- [ ] **Adaptar worker**:
  - Nombre del negocio, industria, tono
  - Opciones del menú / flujo conversacional
  - Zonas, precios, servicios según el cliente
- [ ] **Base Airtable**: crear base o tablas necesarias
  - Tabla Clientes (mínimo: Nombre, Teléfono, Score, Fecha)
  - Tabla del catálogo (Propiedades / Menú / Servicios)
  - Tabla Branding (si tiene redes sociales)
- [ ] **Variables de entorno** en Coolify:
  ```
  YCLOUD_API_KEY (o META_ACCESS_TOKEN)
  NUMERO_BOT_[CLIENTE]
  NUMERO_ASESOR_[CLIENTE]
  AIRTABLE_TOKEN
  AIRTABLE_BASE_[CLIENTE]
  GEMINI_API_KEY
  ```
- [ ] **Registrar router** en `main.py`:
  ```python
  from workers.clientes.[proyecto].[cliente] import worker as [cliente]_worker
  app.include_router([cliente]_worker.router)
  ```
- [ ] **Deploy**: push a `master` → Coolify auto-deploy
- [ ] **Configurar webhook** en YCloud/Meta apuntando al endpoint del worker
- [ ] **Test end-to-end**: mandar "hola" al número y verificar flujo completo
- [ ] **Documentar** en `memory/` el nuevo cliente

### Redes Sociales (comentarios IG/FB)

- [ ] **Page ID** de Facebook del cliente
- [ ] **IG Business Account ID**
- [ ] **Meta App** con permisos `pages_read_engagement`, `instagram_manage_comments`
- [ ] **Webhook Meta** configurado → `https://agentes.arnaldoayalaestratega.cloud/social/meta-webhook`
  - Verify Token: `META_VERIFY_TOKEN` env var
- [ ] **Brandbook en Supabase** tabla `"Datos Proyecto [Cliente]"`:
  ```sql
  INSERT INTO "Datos Proyecto [Cliente]" 
  (page_id, ig_account_id, page_access_token, brand_voice, ...)
  VALUES (...)
  ```
- [ ] **Tabla Branding en Airtable** del cliente con:
  - Colores de marca, tono, industria, logo URL
- [ ] **Test**: publicar comentario en FB/IG y verificar respuesta automática

### Publicación automática de posts (n8n)

- [ ] **Determinar instancia n8n**: Arnaldo (`n8n.arnaldoayalaestratega.cloud`) o Robert (`n8n.lovbot.ai`)
- [ ] **Crear workflow** "Publicar Diario — [Cliente]":
  - Schedule trigger → Brandbook Airtable → Gemini imagen+copy → Cloudinary → FB/IG/LinkedIn
- [ ] **Credenciales en n8n**:
  - Header Auth "Airtable [Cliente]" → `Authorization: Bearer [PAT]`
  - HTTP Request para Meta Graph API
- [ ] **Activar workflow**
- [ ] **Test**: ejecutar manualmente y verificar publicación

## Mapping de proyectos → workers

| "Para quién" | Worker base | Instancia n8n | Coolify |
|--------------|-------------|---------------|---------|
| Arnaldo (propio) | `workers/clientes/arnaldo/` | n8n Arnaldo | Coolify Hostinger |
| Robert / lovbot | `workers/clientes/lovbot/` | n8n lovbot | Coolify Hetzner (Robert) |
| Mica / system-ia | `workers/clientes/system-ia/` | n8n Easypanel | Easypanel Mica |

## Variables de entorno — dónde cargarlas

```bash
# Coolify API (para cargar env vars programáticamente)
TOKEN=$(grep COOLIFY_TOKEN .env | cut -d= -f2)
UUID_APP="[uuid-del-servicio-en-coolify]"

# Listar env vars actuales
curl -s "https://coolify.arnaldoayalaestratega.cloud/api/v1/applications/${UUID_APP}/envs" \
  -H "Authorization: Bearer ${TOKEN}" | jq '.data[] | {key:.key, value:.value}'

# Agregar/actualizar env var
curl -X PATCH "https://coolify.arnaldoayalaestratega.cloud/api/v1/applications/${UUID_APP}/envs" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{"key":"NUEVA_VAR","value":"valor","is_preview":false}'
```

## Documentación final obligatoria

Al terminar el onboarding, actualizar:

1. `memory/infraestructura.md` — agregar el nuevo servicio/endpoint
2. `ai.context.json` — agregar el cliente en `proyectos`
3. `handoff/brief-[cliente].md` — marcar como `status: implementado`
4. Crear `memory/[cliente]-[tipo].md` si el cliente tiene lógica especial

## Preguntas clave para el brief (antes de implementar)

```
1. ¿Cuál es el nombre del negocio y a qué rubro pertenece?
2. ¿Cuál es el número de WhatsApp que van a usar?
3. ¿Tienen logo? ¿Cuáles son los colores de la marca?
4. ¿Qué quieren que haga el bot? (calificar leads / responder preguntas / agendar)
5. ¿Tienen Airtable o hay que crear la base?
6. ¿Tienen cuenta de Meta Business Manager?
7. ¿Quieren publicación automática en redes? ¿En cuáles?
8. ¿Cuál es el número del asesor humano para derivar leads calientes?
```
