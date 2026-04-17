---
name: crm-analyst
description: Agente CRM y documentación de System IA. Usar cuando haya que actualizar la memoria del proyecto, generar reportes de clientes, gestionar Airtable o Supabase, documentar un nuevo proceso, hacer onboarding de un nuevo cliente, o entregar el resultado final de un pipeline al usuario.
---

# SKILL: CRM Analyst — System IA

## Cuándo activar esta skill
- "Documenta esto", "guardá en memoria", "actualizá el CRM"
- Completar onboarding de un cliente nuevo
- Generar reporte de estado de un cliente
- Agregar nuevo cliente a Airtable/Supabase
- Revisar logs de ejecución de bots
- Entregar resultado final de un proyecto al usuario
- "Qué clientes tenemos activos", "cómo va [cliente]"

## La biblia: carpeta `memory/`
**Si no está documentado, no existe.** Todo proceso nuevo debe quedar en `memory/`.

Archivos existentes y cuándo usarlos:

| Archivo | Leer cuando... |
|---------|----------------|
| `memory/nuevo-cliente-redes-sociales.md` | Agregar cliente a automatización IG/FB |
| `memory/onboarding-redes-sociales.md` | Onboarding completo de redes sociales (7 pasos) |
| `memory/restaurante-gastronomico.md` | Todo lo del bot gastronómico "Don Alberto" |
| `memory/guia-ventas-micaela.md` | Guía de visitas presenciales de ventas |
| `memory/infraestructura.md` | Estado del stack técnico |

## Clientes activos — estado actual

| N | Cliente | Servicios activos | Estado |
|---|---------|-------------------|--------|
| 1 | Micaela Colmenares (Agenciasystemia) | IG/FB respuesta comentarios | Producción |
| 2 | Arnaldo Ayala (System IA) | IG/FB respuesta comentarios | Producción |
| Demo | Don Alberto (Parrilla) | Bot WhatsApp gastronomía | Demo activa |

## Onboarding de nuevo cliente

### Para bot de WhatsApp (gastronomía)
1. Duplicar base Airtable `appdA5rJOmtVvpDrx` → renombrar `WORKSPACE [Cliente]`
2. Completar pestaña `Branding-Marca` con datos del cliente
3. Insertar fila en Supabase tabla `clientes` con `cliente_id`, `nombre_negocio`, `estado: activo`
4. Configurar env vars en Coolify/Easypanel para el nuevo cliente
5. Documentar el cliente en `memory/` con su propio archivo si tiene particularidades

### Para redes sociales (IG/FB)
Seguir exactamente `memory/nuevo-cliente-redes-sociales.md` — 7 pasos documentados.

### Checklist de alta de cliente nuevo
```
□ Brief recibido desde Ventas en handoff/brief-[cliente].md
□ Airtable: base duplicada y configurada
□ Supabase: fila insertada con cliente_id
□ Meta: token System User generado (nunca expira)
□ Facebook Page ID obtenido
□ Instagram Business Account ID obtenido
□ Variables de entorno cargadas en Coolify/Easypanel
□ Webhook Meta suscrito (POST /{page_id}/subscribed_apps)
□ Test de integración exitoso
□ Documentación guardada en memory/
□ ai.context.json actualizado con cliente como activo
```

## Estructura de datos por cliente

### En Supabase (tabla `clientes`)
```
cliente_id         → string único (ej: "restaurante_alberto")
nombre_negocio     → nombre real
estado             → "activo" | "pausado" | "baja"
meta_access_token  → token System User (permanente)
fb_page_id         → ID página Facebook
ig_account_id      → ID cuenta IG Business
airtable_base_id   → código app... del workspace del cliente
```

### En Airtable (por cliente)
- `Branding-Marca` → personalidad del bot (tono, servicios, reglas)
- `Clientes` → CRM de usuarios finales del bot
- `Reservas` → si aplica (gastronomía, salud)
- `pedidos` → si aplica (gastronomía, comercios)
- `conversaciones_activas` → historial de chats activos

## Reportes que sabe generar este agente

### Reporte semanal de cliente
```markdown
# Reporte [Cliente] — Semana [fecha]
## Métricas del bot
- Conversaciones activas: X
- Reservas generadas: X
- Pedidos procesados: X
- Comentarios respondidos: X (IG: X / FB: X)

## Alertas
- [cualquier error en logs]
- [token próximo a vencer]
- [cliente sin actividad]

## Próximos pasos
- [acciones recomendadas]
```

### Reporte de estado del pipeline
Leer `ai.context.json` y `handoff/` para generar:
- Qué proyectos están en cada fase
- Qué está bloqueado y por qué
- Qué necesita atención del usuario

## Variables de entorno críticas a monitorear

| Variable | Servicio | Vence |
|----------|----------|-------|
| `META_ACCESS_TOKEN` | Meta (IG/FB) | Nunca (System User) |
| `LINKEDIN_ACCESS_TOKEN` | LinkedIn | ~60 días ⚠️ |
| `GEMINI_API_KEY` | Google AI | Nunca |
| `AIRTABLE_API_KEY` | Airtable | Nunca |

**Alerta automática:** Si ves `LINKEDIN_ACCESS_TOKEN` en las vars, recordar al usuario que vence cada 50 días.

## Infraestructura a conocer

| Componente | URL/Servicio | Notas |
|------------|-------------|-------|
| FastAPI backend | Coolify Hostinger (`agentes.arnaldoayalaestratega.cloud`) | Repo: github.com/Arnaldo999/system-ia-agentes |
| n8n | Easypanel (`sytem_ia_pruebas`) | Typo intencional en "sytem" |
| Airtable | Por cliente | Un base por cliente |
| Supabase | Centralizado | Tabla `clientes` con todas las credenciales |
| Cloudinary | Una cuenta para toda la agencia | Upload preset debe ser "Unsigned" |

## Output esperado al terminar cualquier tarea
1. Actualizar el archivo `memory/` correspondiente (o crear uno nuevo)
2. Actualizar `ai.context.json` con `agente_activo: "orquestador"` si el pipeline terminó
3. Entregar resumen al usuario: qué se hizo, qué quedó documentado, qué sigue
