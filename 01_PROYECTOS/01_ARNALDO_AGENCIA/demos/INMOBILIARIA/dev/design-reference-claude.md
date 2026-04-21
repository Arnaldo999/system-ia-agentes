# Referencia de diseño — Claude Design (pitch 2026-04-20)

**Contexto**: Arnaldo generó en Claude Design un dashboard "CRM Lovbot AI — Inmobiliaria Ros"
con estética Vercel/Linear: fondo `#0b0b14`, gradiente morado→cyan, tipografía Inter +
JetBrains Mono, KPIs con glow, charts de barras, feed de actividad, zonas, pipeline,
chat IA lateral.

El HTML standalone completo (con assets base64, fuentes woff2, SVGs inline y JS) está
descargado en `/tmp/crm-lovbot-standalone.html` (conservar localmente — no se commitea
porque pesa >1MB).

## Plan de port (sesión dedicada futura)

1. **Empezar en DEV**: `demos/INMOBILIARIA/dev/crm.html` (sandbox)
2. Preservar TODA la lógica actual del CRM:
   - Multi-tenant (`SAAS_API`, `API_BASE`, `initTenant()`)
   - Auth PIN (`pinKey`, `submitPin`, `loginScreen`)
   - Fetch endpoints: `/crm/clientes`, `/crm/propiedades`, `/crm/activos`, `/crm/metricas`
   - Upload Cloudinary (preset unsigned)
   - Tabs: Inicio, Leads, Propiedades, Activos, Agenda, Chat IA, Configuración
   - CRUD leads/propiedades/activos
3. **Aplicar diseño**: reemplazar HTML/CSS de cada sección por la versión Claude Design
4. **Mapear datos reales**:
   - KPIs → `/crm/metricas`
   - Chart barras → agregación por día desde `/crm/clientes` (campo Fecha_WhatsApp)
   - Sources bars → campo `Fuente` del lead
   - Pipeline bars → campo `Estado` del lead
   - Zonas → agregación por `Zona` del lead
   - Feed → últimos eventos (nuevos leads, citas, acciones bot)
   - Agenda → leads con `Fecha_Cita != null`
   - Chat IA → ya conectado a n8n webhook existente
5. Preservar branding por tenant (cambia nombre empresa, color, asesor)
6. Test end-to-end con `?tenant=demo` (sandbox compartido Robert)
7. Copiar DEV → PROD cuando Arnaldo valide

## Inspiración visual clave (copiar tal cual)

- Paleta: `#0b0b14` fondo, `#12121f` surface, `#161627` card, `#7c3aed` morado, `#06b6d4` cyan
- Gradiente brand: `linear-gradient(135deg,#7c3aed 0%,#06b6d4 100%)`
- Cards con `border-radius: 12px` + border sutil `rgba(255,255,255,.06)`
- KPIs con barra de color arriba (`::before`) y glow difuso (`::after`)
- Tipografía densa pero legible: Inter 13px base, JetBrains Mono para números
- Sidebar sticky `240px`, topbar sticky con search + status pill
- Chat IA con burbujas tipo ChatGPT + quick actions + textarea auto-expand

## Stack confirmado (no cambia)

- Frontend: HTML + Tailwind-like inline CSS + Vanilla JS
- Backend: FastAPI endpoints `/clientes/lovbot/*` (Robert) y `/clientes/system_ia/demos/inmobiliaria/*` (Mica)
- Multi-tenant: Supabase `tenants` table + `api_url` + `api_prefix`
- Imágenes: Cloudinary unsigned upload
- Chat IA: n8n webhook
