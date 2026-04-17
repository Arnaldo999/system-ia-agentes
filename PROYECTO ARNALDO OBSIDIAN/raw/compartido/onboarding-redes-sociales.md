# 📋 Guía de Onboarding — Automatización de Redes Sociales
> Para copiar en Notion · Versión interna para el equipo de System IA

---

## FASE 0 — Prerequisitos: qué debe tener el cliente ANTES de hablar contigo

### Cuentas obligatorias

- **Instagram** → debe ser cuenta **Business o Creator** (no personal).
  Si es personal, el cliente la convierte así: `Configuración → Cuenta → Cambiar a cuenta profesional`

- **Facebook** → debe tener una **Página de Facebook** (no perfil personal).
  Si no tiene: [facebook.com/pages/create](https://facebook.com/pages/create)

- **LinkedIn** → puede ser perfil personal o Página de empresa.
  ⚠️ El sistema actual publica en **perfil personal** (ver nota multicliente al final)

- **Instagram debe estar conectado a la Página de Facebook** (sin esto, la publicación con imagen falla).
  Se hace desde: `Instagram → Configuración → Cuenta → Cuenta vinculada → Facebook`

---

## FASE 1 — Facebook + Instagram (mismo token, mismo proceso)

### Paso 1.1 — El cliente te da acceso a su Meta Business Manager

#### Opción A (recomendada — cliente te da acceso temporario)

> *"Necesito que me agregues como Administrador en tu Meta Business Manager temporalmente para configurar la integración."*

1. Cliente entra a [business.facebook.com](https://business.facebook.com)
2. `Configuración → Personas → Agregar persona` → pone tu email → rol: **Administrador**
3. También debe asignarte acceso a: su **Página de Facebook** + su **cuenta de Instagram**

#### Opción B (cliente hace todo, tú lo guías)

El cliente sigue la guía de los pasos siguientes y te manda los valores. Usás esta misma guía para indicarle exactamente qué hacer.

---

### Paso 1.2 — Crear la Meta App (una vez por agencia)

Si ya tenés tu app creada para tu propia cuenta, podés reutilizar la misma app. Solo sumás el Facebook Page y el Instagram del cliente como activos en el mismo Business Manager.

**Si es primera vez:**

1. Ir a [developers.facebook.com](https://developers.facebook.com) → **Mis apps → Crear app**
2. Tipo: **Empresa (Business)**
3. Nombre: `"SystemIA Automatizaciones"` (o el nombre de tu agencia)
4. En la app, agregar los productos:
   - **Instagram Graph API** (para IG)
   - **Facebook Login** (para páginas de FB)
5. En `Configuración → Avanzado` → poner la app en modo **Live** (no Development)

> ⚠️ En modo Development solo funciona para tu propio usuario. En modo Live funciona para los clientes.

---

### Paso 1.3 — Crear System User (la forma profesional y permanente)

Un **System User** genera tokens que **nunca expiran** (a diferencia de los tokens de usuario personal que vencen en 60 días).

1. En **business.facebook.com del cliente** → `Configuración del negocio`
2. Lado izquierdo → **Usuarios del sistema → Agregar**
   - Nombre: `SystemIA-Bot` | Rol: **Administrador**
3. Clic en el System User creado → **Generar token de acceso**
4. Seleccionar tu App → Permisos a activar:
   - ✅ `pages_manage_posts`
   - ✅ `pages_read_engagement`
   - ✅ `instagram_basic`
   - ✅ `instagram_content_publish`
   - ✅ `pages_show_list`
5. **Copiar el token** → esto es el `META_ACCESS_TOKEN`
   > ⚠️ ¡Solo se muestra una vez! Guardarlo de inmediato en un lugar seguro.

---

### Paso 1.4 — Obtener los IDs

#### Facebook Page ID

Opción 1 — Visual (más fácil):
- El cliente va a su Página de Facebook → clic en los `...` → "Acerca de esta página" → scroll → ver **ID de página**

Opción 2 — Desde la API:
```
GET https://graph.facebook.com/v22.0/me/accounts?access_token={META_ACCESS_TOKEN}
```
Buscar el campo `id` de la página en la respuesta.

Opción 3 — Desde el Graph Explorer:
- [developers.facebook.com/tools/explorer](https://developers.facebook.com/tools/explorer) → `GET /me/accounts` → copiar el `id`

#### Instagram Business Account ID

Con el `FACEBOOK_PAGE_ID` y el `META_ACCESS_TOKEN` ya obtenidos:

```
GET https://graph.facebook.com/v22.0/{FACEBOOK_PAGE_ID}?fields=instagram_business_account&access_token={META_ACCESS_TOKEN}
```

La respuesta trae el campo `instagram_business_account.id` → ese es el `IG_BUSINESS_ACCOUNT_ID`.

---

## FASE 2 — LinkedIn

LinkedIn es la más compleja porque requiere OAuth. Hay dos métodos:

### Método A — Rápido (para empezar, token dura ~60 días)

1. Crear app en [linkedin.com/developers](https://linkedin.com/developers) → **Create App**
   - Nombre: `"SystemIA Automatizaciones"`
   - LinkedIn Page: la página de tu agencia (o del cliente)
   - Logo: subir logo
2. En la app → pestaña **Products** → solicitar **Share on LinkedIn** → se aprueba de forma inmediata
3. En **Auth** → copiar `Client ID` y `Client Secret`
4. Generar token OAuth:
   - Ir a la herramienta [OAuth 2.0 tools](https://www.linkedin.com/developers/tools/oauth) en la misma consola
   - Seleccionar scopes: `w_member_social`, `openid`, `profile`, `email`
   - Copiar el **Access Token** generado → es el `LINKEDIN_ACCESS_TOKEN`
5. Obtener el **Person ID** → llamar al endpoint de tu agente:
   ```
   GET https://sytem-ia-pruebas-agente.6g0gdj.easypanel.host/debug/linkedin-id
   ```
   (ya debe tener el token cargado en Easypanel)

> ⚠️ **Limitación conocida:** El token de LinkedIn para perfil personal vence en ~60 días.
> **Solución temporal:** Poner un recordatorio en el calendario cada **50 días** para renovar el token y actualizar la variable `LINKEDIN_ACCESS_TOKEN` en Easypanel.

### Método B — Permanente (para producción, más setup)

Para tokens que no vencen necesitás publicar en una **LinkedIn Company Page** con una app aprobada:

1. Solicitar el producto **Community Management API** en la consola (requiere revisión de LinkedIn, puede tardar días o semanas)
2. Usar scope `w_organization_social` en vez de `w_member_social`
3. Los tokens de Company Page no vencen de la misma forma

> 💡 **Recomendación:** Arrancar siempre con el **Método A** para los primeros clientes. Cuando tengas 5+ clientes activos, invertís el tiempo en el Método B.

---

## FASE 3 — Variables de entorno a configurar en Easypanel (por cliente)

| Variable | De dónde sale |
|---|---|
| `META_ACCESS_TOKEN` | Token del System User (Paso 1.3) |
| `IG_BUSINESS_ACCOUNT_ID` | ID de la cuenta Business de Instagram (Paso 1.4) |
| `FACEBOOK_PAGE_ID` | ID de la Página de Facebook (Paso 1.4) |
| `LINKEDIN_ACCESS_TOKEN` | Token OAuth de LinkedIn (Fase 2) |
| `LINKEDIN_PERSON_ID` | Llamada a `GET /debug/linkedin-id` del agente |
| `CLOUDINARY_CLOUD_NAME` | Panel de Cloudinary — una sola cuenta para toda la agencia está bien |
| `CLOUDINARY_UPLOAD_PRESET` | Cloudinary → Settings → Upload Presets → crear preset tipo **Unsigned** |
| `GEMINI_API_KEY` | [aistudio.google.com](https://aistudio.google.com) → Get API Key |

> ⚠️ **CLOUDINARY_UPLOAD_PRESET debe ser de tipo "Unsigned"** — si es "Signed" la subida falla sin autenticación adicional.

---

## FASE 4 — Checklist de verificación antes de activar

```
□ Cargar todas las variables de entorno en Easypanel

□ Verificar variables: GET https://{tu-agente}.easypanel.host/debug/env
  → todas deben mostrar ✅

□ Verificar LinkedIn Person ID: GET https://{tu-agente}.easypanel.host/debug/linkedin-id
  → debe devolver el LINKEDIN_PERSON_ID correcto

□ Prueba completa: POST a /social/publicar-completo con los datos de marca del cliente
  → revisar respuesta JSON: buscar "imagen_url" con una URL de Cloudinary

□ Verificar en Instagram que el post apareció CON IMAGEN 📸

□ Verificar en LinkedIn que el post apareció (solo texto — es el comportamiento actual)

□ Verificar en Facebook que el post apareció con imagen 📸

□ Confirmar que llegó la notificación de WhatsApp ✅

□ Activar el workflow de n8n (Schedule Trigger → 9:00am) ✅
```

---

## ⚠️ NOTA IMPORTANTE — Arquitectura actual vs. multicliente

El sistema actual tiene **variables de entorno únicas** → corre los posts de **UN solo cliente por deployment**.

Para manejar múltiples clientes tenés dos opciones:

| Opción | Pro | Contra |
|---|---|---|
| **Un deployment por cliente en Easypanel** | Simple, rápido de implementar y vender | Más costo de servidor (≈$5-10/mes por cliente) |
| **Refactorizar a multicliente** | Escala mejor, un solo servidor para N clientes | Requiere trabajo de código (2-3 días) |

> 💡 **Para los primeros 3-5 clientes**: la opción de un deploy por cliente es la más rápida de implementar y vender. Hacés el switch a multicliente cuando el negocio lo justifique.

---

## 🔗 Links útiles de referencia

- [Meta Business Manager](https://business.facebook.com)
- [Meta Developers](https://developers.facebook.com)
- [Graph API Explorer](https://developers.facebook.com/tools/explorer)
- [LinkedIn Developers](https://linkedin.com/developers)
- [LinkedIn OAuth Tools](https://www.linkedin.com/developers/tools/oauth)
- [Cloudinary](https://cloudinary.com)
- [Google AI Studio (Gemini API Key)](https://aistudio.google.com)
- [Agente System IA — debug/env](https://sytem-ia-pruebas-agente.6g0gdj.easypanel.host/debug/env)
- [Agente System IA — debug/linkedin-id](https://sytem-ia-pruebas-agente.6g0gdj.easypanel.host/debug/linkedin-id)
