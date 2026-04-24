# Setup — Social Automation para Back Urbanizaciones

> **Fecha**: 2026-04-23
> **Cliente**: Maicol — Back Urbanizaciones
> **Objetivo**: Posts automáticos en Facebook + Instagram + bot de comentarios automáticos
> **Estado actual**: 85% configurado — bloqueado 7 días por regla Meta

---

## 1. Activos configurados ✅

### BM Meta Business
- **BM ID**: `1633606387950668`
- **Nombre**: Back Urbanizaciones
- **Admins actuales**: Maicol Back + Arnaldo Ayala
- **System Users**: _pendiente crear_

### Página Facebook
- **Page ID**: `985390181332410`
- **Nombre**: Back Urbanizaciones
- **Admins**: Arnaldo + Maicol (Control total)

### Instagram Business
- **Account ID**: `17841432226033990`
- **Handle**: @backurbanizaciones
- **Admins**: Arnaldo + Maicol (Control total)

### Cuenta Publicitaria
- Admins: Arnaldo + Maicol (Control total)
- _Para ads futuros, no prioritario ahora_

### App Meta Developer
- **Nombre**: Social Media Automator AI
- **App ID**: `895855323149729`
- **Dueño**: BM Emprender en lo Digital (Arnaldo)
- **Compartida con**: BM Back Urbanizaciones (permisos: Desarrollar + Probar + Ver estadísticas)

### Airtable Branding (Back Urbanizaciones)
- **Base ID**: `appaDT7uwHnimVZLM`
- **Tabla Branding ID**: `tbl0QeaY3oO2P5WaU`
- **Record Back_Urbanizaciones**: `rec8ZOSA7fZaAQAd4`
- Campos completos: Logo, Industria, Servicio, Público, Tono, Reglas, Estilo Visual, Colores, CTA, Facebook Page ID, IG Business Account ID ✅

---

## 2. Bloqueo actual ⚠️

**Regla de Meta**: Los admin del BM agregados recientemente deben esperar **7 días de antigüedad** antes de poder crear System Users con rol Admin.

Arnaldo fue agregado como admin al BM Back Urbanizaciones el **2026-04-23**. Podrá crear System User Admin a partir del **2026-04-30**.

**Workaround**: Maicol (admin original del BM, con >7 días de antigüedad) puede crear el System User sin esta restricción.

---

## 3. Acción pendiente — crear System User

### Si Maicol lo crea (recomendado, desbloquea inmediato):

1. Meta Business Suite → Back Urbanizaciones → Configuración
2. Usuarios → Usuarios del sistema
3. Click **+ Agregar**
4. Nombre: `BackUrban Automation`
5. Rol: **Admin**
6. Crear

### Después de crear el System User (quien lo haga):

1. Click en `BackUrban Automation`
2. **Asignar activos**:
   - Página Facebook (Back Urbanizaciones) — Control total
   - Cuenta Instagram (@backurbanizaciones) — Control total
   - Cuenta Publicitaria — Admin (opcional)
3. **Generar nuevo token**:
   - App: **Social Media Automator AI** (895855323149729)
   - Caducidad: **Nunca**
   - Permisos (scopes obligatorios):
     - `pages_manage_posts`
     - `pages_manage_engagement`
     - `pages_read_engagement`
     - `pages_read_user_content`
     - `pages_show_list`
     - `instagram_basic`
     - `instagram_content_publish`
     - `instagram_manage_comments`
     - `instagram_manage_insights`
     - `business_management`
4. Copiar el token (largo, empieza con `EAA...`)
5. **IMPORTANTE**: Meta lo muestra UNA sola vez. Guardarlo inmediatamente.

---

## 4. Cargar en Supabase — SQL INSERT

Una vez generado el token, ejecutar en Supabase → SQL Editor:

```sql
INSERT INTO clientes (
  cliente_id,
  nombre_negocio,
  estado,
  meta_access_token,
  fb_page_id,
  ig_account_id,
  whatsapp_numero_notificacion,
  airtable_base_id,
  airtable_table_id,
  created_at,
  updated_at
) VALUES (
  'Back_Urbanizaciones',
  'Back Urbanizaciones',
  'activo',
  'EAA...PEGAR_TOKEN_AQUI...',
  '985390181332410',
  '17841432226033990',
  '5493764815689',
  'appaDT7uwHnimVZLM',
  'tbl0QeaY3oO2P5WaU',
  NOW(),
  NOW()
);
```

**Verificar después**:
```sql
SELECT cliente_id, nombre_negocio, estado, fb_page_id, ig_account_id, airtable_base_id
FROM clientes
WHERE cliente_id = 'Back_Urbanizaciones';
```

---

## 5. Workflow n8n — duplicar del de Arnaldo

### Pasos

1. Entrar al n8n de Arnaldo (`n8n.arnaldoayalaestratega.cloud` o similar)
2. Buscar workflow: `📱 Arnaldo — Publicación Diaria Redes Sociales (IG + FB + LI)` (ID: `aJILcfjRoKDFvGWY`)
3. Click en "..." → **Duplicar**
4. Renombrar: `📱 Maicol — Publicación Diaria Redes Sociales (Back Urbanizaciones)`
5. Editar node **📋 Obtener Brandbook Arnaldo** → renombrar a `📋 Obtener Brandbook Back Urbanizaciones`
6. En ese node cambiar URL:
   - De: `https://api.airtable.com/v0/appOUtGnMYHrbLaMa/tblgFvYebZcJaYM07?maxRecords=1`
   - A: `https://api.airtable.com/v0/appaDT7uwHnimVZLM/tbl0QeaY3oO2P5WaU?maxRecords=1`
7. Crear nueva credencial Airtable:
   - Tipo: **Header Auth**
   - Nombre: `Header Auth Airtable Maicol`
   - Header Name: `Authorization`
   - Header Value: `Bearer <AIRTABLE_TOKEN_MAICOL>` (usar token `patL8...` ya en .env)
8. Asignar esa credencial al node
9. El node `🚀 Publicar en Redes` **no necesita cambios** — el endpoint `/social/publicar-completo` resuelve credenciales por `cliente_id` automáticamente
10. Ajustar el horario del schedule si se quiere (ej: 10am en vez de 9am para no competir con posts de Arnaldo)
11. **NO activar** hasta que el token esté cargado en Supabase
12. Una vez activo, trigger manual para testear el primer post

---

## 6. Orden de ejecución final

| # | Acción | Quién | Tiempo | Bloquea |
|---|--------|-------|--------|---------|
| 1 | Pedir a Maicol que cree System User Admin | Arnaldo | 1 min | — |
| 2 | Crear System User `BackUrban Automation` en BM Back Urbanizaciones | Maicol | 2 min | Sí |
| 3 | Asignar activos (FB Page + IG + Ad Account) al System User | Arnaldo | 2 min | Sí |
| 4 | Generar token permanente con app Social Media Automator AI | Arnaldo | 2 min | Sí |
| 5 | Insertar registro en Supabase tabla `clientes` | Arnaldo | 2 min | Sí |
| 6 | Duplicar workflow n8n → renombrar → cambiar URL Airtable | Arnaldo | 5 min | No (paralelo) |
| 7 | Crear credencial Airtable Maicol en n8n | Arnaldo | 2 min | No (paralelo) |
| 8 | Activar workflow n8n | Arnaldo | 1 min | Sí |
| 9 | Trigger manual para test primer post | Arnaldo | 2 min | — |
| 10 | Validar publicación en FB + IG | Arnaldo | 3 min | — |

**Total estimado**: 22 min (una vez Maicol crea el System User)

---

## 7. Post-setup — verificación

### Chequeos obligatorios después del primer post

- [ ] El post se publicó en la Página Facebook Back Urbanizaciones
- [ ] El post se publicó en Instagram @backurbanizaciones
- [ ] La imagen generada respeta paleta de marca (verde oscuro + dorado)
- [ ] El copy respeta tono (cercano, confiable, experto) y reglas estrictas (no promete valorización garantizada)
- [ ] El CTA incluye link al WhatsApp correcto del bot
- [ ] El hashtags son relevantes a inmobiliaria/lotes/Misiones

### Si falla algún paso

- **Error en workflow n8n**: revisar logs del Telegram alert (chat_id `863363759`)
- **Error en publicación**: revisar logs Coolify `system-ia-agentes`
- **Imagen rota**: revisar `GEMINI_API_KEY` en Coolify
- **Credenciales inválidas**: regenerar token System User con los 10 scopes correctos

---

## 8. Próximos pasos (fuera de scope del setup inicial)

### Semana 1 post-setup
- [ ] Monitorear que los 7 primeros posts salgan OK
- [ ] Ajustar temas del día según lo que funcione mejor (tabla `_get_tema_del_dia` en worker social)
- [ ] Crear 5-10 templates de posts específicos para Back Urbanizaciones en Airtable

### Semana 2
- [ ] Activar bot de comentarios automático (webhook Meta + respuestas IA)
- [ ] Configurar Meta Webhooks en app → endpoint `POST /social/meta-webhook`
- [ ] Integrar comentarios → DM privado con bot calificador → CRM Airtable Maicol

### Semana 3-4
- [ ] Primera campaña Meta Ads (click to WhatsApp) con presupuesto bajo (USD 30-50)
- [ ] Configurar pixel de conversión
- [ ] Retargeting a usuarios que interactuaron con posts orgánicos

---

## 9. Referencias

- Backend worker social: `backends/system-ia-agentes/workers/social/worker.py`
- Supabase project: `pczrezpmdugdsjrxspjh` (ArnaldoAyalaAgencia)
- Workflow base n8n: `aJILcfjRoKDFvGWY` (📱 Arnaldo — Publicación Diaria)
- Airtable base Maicol: `appaDT7uwHnimVZLM`
- Airtable tabla Branding Maicol: `tbl0QeaY3oO2P5WaU`
- Record Back_Urbanizaciones: `rec8ZOSA7fZaAQAd4`
- Endpoint maestro: `POST /social/publicar-completo`
- App Meta: `Social Media Automator AI` (895855323149729)
