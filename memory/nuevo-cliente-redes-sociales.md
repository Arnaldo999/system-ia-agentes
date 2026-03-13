# Requisitos para sumar nuevo cliente — Automatización de Redes Sociales

## Arquitectura del sistema (SaaS Multi-Tenant)
- **Supabase (La Bóveda)**: Tabla central `clientes` que almacena `meta_access_token`, IDs y el `airtable_base_id` único por cliente.
- **Airtable (Hub del Cliente)**: Cada cliente tiene una Base (Workspace) exclusiva (con su propio ID `app...`).
- **Render / FastAPI (Cerebro Stateless)**: Recibe el `cliente_id` u origen webhooks, consulta Supabase en vivo y procesa. NO almacena credenciales de clientes en el `.env`.
- **n8n (Orquestador)**: En rutas programadas (cron), usa el nodo Loop para procesar un cliente a la vez, garantizando aislamiento total.
- **Webhook URL Meta**: Dirigido al worker FastAPI en Render.

---

## PASO 1 — Información a pedirle al cliente

### Datos de marca (para Airtable)
- [ ] Nombre comercial
- [ ] Servicio principal que ofrece
- [ ] Tono de voz (ej: profesional, cercano, juvenil, experto)
- [ ] Público objetivo
- [ ] Reglas estrictas / cosas que NO debe decir el bot

### IDs de cuentas Meta (el cliente los consigue en Meta)
- [ ] **Facebook Page ID** → Configuración de la página → Información de la página → ID
- [ ] **Instagram Business Account ID** → Meta Business Suite → Instagram → Configuración

---

## PASO 2 — Conectar al Business Manager (token permanente)

El System User token ya existente cubre páginas nuevas si se agrega la página al Business Manager.

**Opción A (recomendada):** Cliente agrega tu BM como socio
1. Cliente va a su Facebook Page → Configuración → Página de negocios
2. Agrega `355106379054248` (tu Business ID) como socio con acceso total
3. Tú vas a `business.facebook.com` → Configuración → Usuarios del sistema → SocialMedia → Agregar activos → seleccionar la nueva página

**Opción B:** El cliente genera su propio System User token
- Token debe tener permisos: `pages_read_engagement`, `pages_manage_posts`, `pages_read_user_content`, `pages_manage_engagement`, `instagram_manage_comments`, `instagram_basic`
- Token del tipo System User (permanente, no vence)

---

## PASO 3 — Airtable (Hub del Cliente)

En lugar de mezclar todos los clientes en una tabla masiva, darle su propio "Edificio":
1. Duplicar la Base maestra de operaciones (ej. "WORKSPACE SYSTEM IA") y nombrarla "WORKSPACE [Nombre Cliente]".
2. Dejar UNA SOLA FILA en la pestaña de `Branding-Marca`.
3. Rellenar los campos: Nombre Comercial, Servicio Principal, Tono de Voz, Público Objetivo, Reglas Estrictas.
4. **COPIAR EL BASE ID**: De la URL del navegador, copiar la parte que dice `appXXXXXXXXXXXXX`.

---

## PASO 4 — Supabase (Carga de Credenciales Seguras)

Ya **NO** usamos el archivo `.env` en Easypanel para guardar clientes uno por uno.
Ir al Dashboard de Supabase (Editor de Tablas -> tabla `clientes`) e insertar una nueva fila con:

- `cliente_id`: string único para el sistema (ej. `clinica_sur`)
- `nombre_negocio`: Nombre real
- `estado`: `activo`
- `meta_access_token`: Token permanente del Paso 2
- `fb_page_id`: ID de la página de FB
- `ig_account_id`: ID de la cuenta IG
- `airtable_base_id`: El código `app...` copiado en el Paso 3.


---

## PASO 5 — Suscribir Facebook Page al webhook

En Graph API Explorer con el **page token** de la nueva página:

```
# Primero obtener el page token:
GET /{new_page_id}?fields=access_token&access_token={META_TOKEN}

# Luego suscribir:
POST /{new_page_id}/subscribed_apps?subscribed_fields=feed&access_token={PAGE_TOKEN}
```

Debe responder `{"success": true}`.

---

## PASO 6 — Instagram (automático)

La suscripción de `comments` en Meta Developers es a nivel de app — cubre automáticamente cualquier cuenta de Instagram conectada al Business Manager. No requiere acción adicional.

---

## PASO 7 — n8n (si también publica contenido)

Si el cliente también usa publicación automática de posts:
1. Duplicar el workflow "Publicar en Redes (Easypanel)"
2. Apuntar al Brand Book del nuevo cliente en Airtable
3. Configurar el schedule según días/horarios acordados

---

## Clientes activos

| N | Cliente | FB Page ID | IG Account ID | Env vars |
|---|---------|-----------|---------------|----------|
| 1 (base) | Micaela Colmenares (Agenciasystemia) | 1010424822153264 | 17841480610317297 | META_ACCESS_TOKEN, FACEBOOK_PAGE_ID, IG_BUSINESS_ACCOUNT_ID |
| 2 | Arnaldo Ayala (System IA) | 355053299059556 | 17841452133822887 | CLIENT_2_META_TOKEN, CLIENT_2_PAGE_ID, CLIENT_2_IG_ID |

---

## Notas importantes

- **Likes automáticos**: NO disponibles en la API oficial de Meta. No intentar implementar.
- **Tokens**: Siempre System User (permanente). Nunca tokens del Graph API Explorer (expiran en 1h).
- **Facebook reply endpoint**: `POST /{comment_id}/comments` (NO /replies — eso es solo Instagram)
- **Instagram reply endpoint**: `POST /{comment_id}/replies`
- **Facebook**: El webhook no envía el texto del comentario — hay que buscarlo con `GET /{comment_id}?fields=message`
- **Page token vs User token**: Facebook Page operations requieren Page Access Token. El código hace el intercambio automáticamente via `_get_page_token()`.
