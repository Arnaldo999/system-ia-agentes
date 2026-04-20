---
title: "Meta Business Portfolio — Verificación del negocio (paso 0)"
tags: [meta, business-portfolio, verificacion, onboarding-cliente, sop, documentacion-oficial]
source_count: 1
proyectos_aplicables: [robert, arnaldo, mica]
---

# Meta Business Portfolio — Verificación del negocio (paso 0)

## Definición

El **Business Portfolio** (antes "Business Manager") es la **identidad legal** de un negocio ante Meta. Contiene todos sus activos: números WhatsApp, plantillas de mensajes, cuentas publicitarias, píxeles, y apps de Meta Developers.

**Meta exige portfolio verificado** para cualquier uso avanzado de la API (Tech Provider, WhatsApp Coexistence, Cloud API directa, templates aprobadas). No es opcional, sin importar si usás YCloud, Twilio, Evolution, o API directa — tarde o temprano aparece.

Panel: `business.facebook.com`

## Quién lo necesita

**TODOS los que manejan WhatsApp Business o Meta Ads con fines comerciales**:

- ✅ [[lovbot-ai]] (Robert) — portfolio verificado, ya es Tech Provider
- ❓ [[agencia-arnaldo-ayala]] (vos) — confirmar si tiene portfolio propio verificado (necesario si querés ofrecer Cal.com/YCloud con números propios a clientes)
- ❓ [[system-ia]] (Mica) — confirmar si tiene portfolio propio (si no, todos los bots de Evolution API viven bajo el portfolio de Evolution, no el de Mica)
- ✅ Cada **cliente final** de las 3 agencias necesita su PROPIO portfolio verificado si quiere:
  - Tener su número conectado oficialmente
  - Usar WhatsApp Coexistence
  - Recibir templates pre-aprobadas
  - Evitar baneos de Meta por número desvinculado

## ⚠️ Regla irrompible de Kevin

**Meta es rápido aprobando negocios bien presentados (1-3 días), PERO extremadamente lento para desbloquear si te banea (meses o años).**

→ **Hacerlo bien el primer intento es crítico.** Kevin estuvo 2 años apelando una cuenta publicitaria bloqueada.

## SOP — Verificación paso-a-paso

### Paso 1 — Crear el portfolio
1. Ir a `business.facebook.com`
2. Login con cuenta personal Meta
3. Menú izquierdo → **"Crear portafolio comercial"**

### Paso 2 — Datos del portfolio

| Campo | Qué poner | Trampa |
|---|---|---|
| Nombre portfolio | Nombre **comercial/marca** visible | Acá va el brand, no el legal |
| Nombre contacto | Persona real (dueño o responsable legal) | Debe poder recibir email |
| Email contacto | **Dominio propio** `contacto@tudominio.com` | 🚨 NO usar gmail/hotmail — Meta desconfía |

### Paso 3 — Iniciar verificación

Dentro del portfolio recién creado → **"Centro de seguridad"** → **"Iniciar verificación"** → "Empezar".

### Paso 4 — País + tipo empresa

- **País**: donde está dada de alta legalmente la empresa (debe coincidir con los docs que subís).
- **Tipo**: "Empresa privada" (mayoría de casos). "Persona física" si es autoempleado. Otras opciones solo si corresponde exacto.

### Paso 5 — Datos legales

| Campo | Qué poner |
|---|---|
| **Nombre legal** | EXACTO como aparece en el documento oficial (sin abreviaturas ni typos) |
| **Nombre comercial** | La marca pública / nombre de fantasía |

Ejemplo persona física: nombre legal = nombre completo; nombre comercial = "AISH Automation Agency".

### Paso 6 — Dirección fiscal

**Copiar 100% EXACTO la dirección del documento legal.** Incluso typos del organismo fiscal — si el doc dice "Av. Corrrientes 1234" con 3 erres, acá va con 3 erres.

🚨 Error #1 de rechazo: dirección no coincide al 100% con el doc.

### Paso 7 — Teléfono + sitio web

- **Teléfono**: número real del negocio/responsable legal.
- **Sitio web**: OBLIGATORIO si querés Tech Provider o Coexistence después. Debe tener:
  - Aviso de privacidad (URL pública)
  - Términos y condiciones
  - Política de eliminación de datos

(Lovbot ya tiene estos 3 en `lovbot.mx` + `lovbot-legal.vercel.app` — reutilizable como ejemplo.)

### Paso 8 — Verificación contacto

Meta manda código a email / SMS / WhatsApp → pegar código para continuar.

### Paso 9 — Subir documento oficial

Meta muestra los documentos aceptados según el país. **Usar el recomendado** (marcado con estrella).

Ejemplos por país:
- 🇲🇽 México → Constancia de Situación Fiscal (SAT)
- 🇦🇷 Argentina → CUIT + constancia AFIP/ARCA
- 🇨🇴 Colombia → RUT (DIAN)
- 🇨🇱 Chile → Inicio de Actividades SII
- 🇵🇪 Perú → Ficha RUC (SUNAT)

Reglas del documento:
- **Legible** (alta resolución)
- **Digital** preferido
- **Reciente** (máx 3 meses de antigüedad)

### Paso 10 — Comprobante domicilio (si lo pide)

Meta a veces pide comprobante adicional:
- Recibo luz / agua / internet
- **Misma dirección** que el documento legal (100% match)
- Legible, reciente

### Paso 11 — Enviar + esperar

Tiempo normal: **1-3 días hábiles**.

### Paso 12 — Verificado ✅

Estado en el panel cambia a "Empresa verificada". Desbloquea:
- Apps Meta Developers
- Tech Provider application
- WhatsApp Coexistence
- Cloud API oficial

## Errores más comunes de rechazo (orden de frecuencia)

1. **Dirección no coincide** con el documento fiscal (100% exacto requerido)
2. **Email genérico** (gmail/hotmail/yahoo) en vez de dominio propio
3. **Documento poco legible** o fotocopia/foto mala calidad
4. **Documento viejo** (>3 meses antigüedad)
5. **Nombre legal con typo** o abreviado (ej: "S.A." en vez de "Sociedad Anónima")
6. **Sitio web sin páginas legales** publicadas
7. **Tipo de empresa mal elegido** (ej: "cotiza en bolsa" cuando sos pyme)
8. **País no coincide** con el documento fiscal

## Consideración para Tech Provider (siguiente nivel)

Una vez verificado el portfolio, **SE PUEDE** aplicar para ser Tech Provider. Pero requiere:
- Páginas legales públicas (privacidad + términos + eliminación datos)
- Meta App creada y vinculada al portfolio
- Access Verification (~5 días adicionales)

Ver [[meta-tech-provider-onboarding]] para el siguiente paso.

## 🚫 Evolution API como alternativa al portfolio verificado

Kevin lo desaconseja explícitamente. Razones:
- No es API oficial → emula navegador WhatsApp Web → Meta puede detectar y banear
- Kevin reporta bugs recurrentes, está migrando clientes a API oficial
- Sin garantía de estabilidad a largo plazo

**En el ecosistema Arnaldo**: [[micaela-colmenares]] usa [[evolution-api]] por pragmatismo (sin Business Portfolio propio aún). Esto es aceptable para demos y pruebas, pero **no escala** a clientes que paguen por estabilidad. Plan de mediano plazo: verificar portfolio Mica + migrar a Coexistence via Tech Provider propio o vía Robert.

## Cuándo aplica cada ruta

| Escenario | Ruta correcta |
|---|---|
| Cliente nuevo de Robert (Lovbot) | Cliente verifica SU portfolio → Robert lo onboardea vía Embedded Signup con Coexistence |
| Arnaldo quiere número propio oficial WhatsApp | Verificar portfolio Arnaldo + crear app Meta + conectar número |
| Mica quiere abandonar Evolution | Verificar portfolio Mica + opción A: Tech Provider propio (5 días extra) o opción B: usar Robert como TP y rutear números via override |
| Cliente de Mica quiere número oficial | Cliente verifica SU portfolio + Mica lo onboardea |

## Relaciones

- [[meta-tech-provider-onboarding]] — siguiente paso post-verificación
- [[meta-webhooks-compliance]] — compliance que requieren apps Tech Provider
- [[evolution-api]] — alternativa no oficial (desaconsejada por Kevin)
- [[ycloud]] — BSP que NO requiere portfolio propio del cliente (YCloud maneja su portfolio global)
- [[lovbot-ai]] / [[agencia-arnaldo-ayala]] / [[system-ia]] — las 3 agencias del ecosistema

## 💡 Oportunidad de negocio (nota estratégica)

Kevin menciona: *"las empresas cobran miles de dólares por esta asesoría de cómo ser tech provider"*. Si Robert ya es TP verificado y tiene toda la infra lista (webhooks + compliance + onboarding), **puede vender este mismo SOP como servicio premium** a agencias que no quieran pasar por el proceso de 5-10 días.

Alternativamente: ofrecer "WhatsApp oficial llave en mano" a clientes finales (ellos verifican su portfolio, Robert los onboardea en minutos).
