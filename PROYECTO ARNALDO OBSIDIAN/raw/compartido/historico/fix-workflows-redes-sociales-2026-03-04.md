# Fix Workflows Redes Sociales — 2026-03-04

## Resumen

Se corrigieron los dos workflows de publicación automática en redes sociales
para que publiquen correctamente en **Instagram**, **Facebook** y **LinkedIn**.

---

## Workflows corregidos

### 1. 🚀 Automatizar Redes Sociales - social-systemia

**Estado:** ✅ Funcionando (Instagram + Facebook)
**LinkedIn:** ⏸️ Pendiente (Mica aún no conectó la página de LinkedIn)

**Cambios realizados:**
- Corregido el JSON body del nodo HTTP Request "Publicar en Redes (Easypanel)"
- Expresión correcta: `{{ { "cliente_id": $json["ID Cliente"], "datos_marca": $json } }}`
- URL actualizada a Render: `https://system-ia-agentes.onrender.com/social/publicar-completo`
- Credenciales de Airtable configuradas correctamente

### 2. 🚀 Automatizar Redes Sociales (Arnaldo)

**Estado:** ✅ Funcionando (Instagram + Facebook + LinkedIn)

**Cambios realizados:**
- Corregido el JSON body (era el error principal)
- Credenciales de Airtable cambiadas al token global → base "WORKSPACE Arnaldo Ayala" → tabla "Branding-Marca"
- URL actualizada de Easypanel a Render: `https://system-ia-agentes.onrender.com/social/publicar-completo`

---

## Causa raíz del error

### Error: "JSON parameter needs to be valid JSON"
- **Problema:** El campo JSON del nodo HTTP Request usaba `$vars.META_ACCESS_TOKEN` etc., que no existen en n8n self-hosted
- **Solución:** Simplificar el body a solo `cliente_id` + `datos_marca`. El worker busca las credenciales automáticamente en Supabase.

### Error: "Falta ig_id o token_de_acceso" / "Faltan credenciales de LinkedIn"
- **Problema:** Se usó `JSON.stringify()` en la expresión del body, lo que hacía que n8n enviara un string escapado en vez de un objeto JSON
- **Solución:** Quitar `JSON.stringify()` y usar solo `{{ { ... } }}` (objeto JavaScript directo)

---

## Expresión correcta para el JSON body (nodo HTTP Request)

```javascript
// ✅ CORRECTO — n8n serializa automáticamente el objeto a JSON
{{ { "cliente_id": $json["ID Cliente"], "datos_marca": $json } }}

// ❌ INCORRECTO — stringify causa doble serialización
{{ JSON.stringify({ "cliente_id": $json["ID Cliente"], "datos_marca": $json }) }}
```

---

## Flujo de credenciales (cómo el worker decide qué tokens usar)

```
1. ¿n8n mandó bloque "credenciales" con meta_access_token lleno?
   → Usa esas credenciales (para workflows que pasan tokens explícitos)

2. ¿Supabase tiene registro para este cliente_id?
   → Usa las credenciales de Supabase (tabla "clientes")
   → ESTE ES EL CAMINO QUE USAN AMBOS WORKFLOWS AHORA

3. ¿Nada de lo anterior?
   → Usa env vars globales de Render (fallback de seguridad)
   → LinkedIn queda en None (no funciona por esta vía)
```

---

## Arquitectura actual

| Componente | Tecnología | Función |
|-----------|-----------|---------|
| **Orquestador** | n8n (Self-Hosted, Easypanel) | Dispara el workflow, trae Brand Book de Airtable, llama al worker |
| **Cerebro** | FastAPI (Render) | Genera textos IA (Gemini), genera imagen, sube a Cloudinary, publica en redes |
| **Bóveda** | Supabase (PostgreSQL) | Almacena credenciales por cliente (meta_access_token, fb_page_id, etc.) |
| **CMS** | Airtable | Brand Book por cliente (tono de voz, industria, reglas, logo, etc.) |

---

## Próximos pasos (cuando se sumen más clientes)

- [ ] Crear workflow maestro unificado con Loop/Split In Batches
- [ ] El master lee todos los clientes de Supabase y los procesa uno por uno
- [ ] Eliminar la necesidad de duplicar workflows por cliente
- [ ] Agregar tabla `publicaciones_log` en Supabase para auditoría

---

## IDs de ejecuciones exitosas (para referencia)

- **System IA:** Ejecución exitosa ~19:08 (4 Mar 2026) — IG ✅, FB ✅
- **Arnaldo:** Ejecución #958 exitosa ~23:33 (4 Mar 2026) — IG ✅, FB ✅, LI ✅
  - Instagram post_id: `18346681630238581`
  - LinkedIn post_id: `urn:li:share:7435150927344599040`
