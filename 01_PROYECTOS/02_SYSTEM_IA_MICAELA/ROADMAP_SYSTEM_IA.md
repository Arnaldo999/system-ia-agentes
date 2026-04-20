# Roadmap System IA — Estado actual y próximos pasos

> **Para**: Micaela Colmenares
> **De**: Arnaldo (socio técnico)
> **Fecha**: 20 de abril 2026

---

## 🎯 Resumen en 30 segundos

Ya tenés **toda la infraestructura técnica** para empezar a vender bots de WhatsApp con IA a tus clientes. Hoy podés:

1. Mandarle a un prospecto el link del **brief** para que lo complete.
2. Correr **un comando** para activarle el bot.
3. Enviarle otro link para que se **conecte él mismo** en 1 minuto.

Tu cliente termina con:
- Un **bot en su WhatsApp** que responde con IA 24/7 y califica leads.
- Un **CRM** donde ve todos los leads y propiedades.
- **Chatwoot** para cuando quiera responder manualmente.

Todo funcionando, sin que tengas que tocar nada técnico.

---

## 📍 ¿En qué estado está hoy cada pieza?

### ✅ LISTO (podés usar ya)

| Pieza | Para qué sirve | Link |
|---|---|---|
| **Formulario de brief** | El cliente completa sus datos (negocio, asesor, productos, tono del bot) y descarga un archivo | [systemia-brief-form.vercel.app](https://systemia-brief-form.vercel.app) |
| **Página de conexión WhatsApp** | El cliente entra, ve su QR y escanea con su celular para conectar | [systemia-onboarding.vercel.app](https://systemia-onboarding.vercel.app) |
| **Bot demo inmobiliaria** | Un bot funcionando que responde, califica leads BANT, busca propiedades y agenda citas con Cal.com | Número Demos conectado |
| **CRM con IA** | Panel donde vos y el cliente ven leads, propiedades, citas y un chat de IA que contesta preguntas sobre sus datos | Vinculado al worker |
| **Base de datos Airtable** | Donde viven todos los datos de los clientes (leads, propiedades, sesiones del bot, clientes de tu agencia) | `appA8QxIhBYYAHw0F` |
| **Script de activación** | Un comando que al correrlo registra al cliente nuevo y te genera el mensaje listo para mandarle | `onboard_mica_cliente.py` |

### 🟡 EN PROGRESO (funciona pero manual)

| Pieza | Estado |
|---|---|
| **Crear inbox Chatwoot para cada cliente** | Hoy lo hacés a mano en Chatwoot (2 minutos). En la versión próxima lo va a hacer el script automáticamente. |
| **Auditoría diaria del ecosistema Mica** | El sistema existe y corre cada mañana, pero faltan unos chequeos específicos tuyos. |

### 🔮 FUTURO (cuando aprueben a Robert)

| Pieza | Cuándo |
|---|---|
| **Conexión WhatsApp oficial (sin QR)** | Cuando Meta apruebe a Robert como Tech Provider (2-10 días desde el 19 de abril). En ese momento, los clientes podrán conectar su WhatsApp con un login oficial Meta en vez de escanear QR. Más profesional, más estable, sin riesgo de baneo. |

---

## 🔄 Flujo completo "cliente nuevo" — paso a paso

### 👤 Paso 1 — Mica habla con el prospecto

Conversación normal de ventas. Cuando el cliente dice "sí, lo contrato":
- Le mandás el link del **formulario de brief**: https://systemia-brief-form.vercel.app
- Le explicás que va a completar 8 secciones en 5 minutos.

### 📝 Paso 2 — Cliente completa el brief (autónomo)

El cliente completa:
1. **Identidad**: nombre del negocio, ciudad, descripción
2. **Asesor**: quién va a recibir los leads calificados
3. **Vertical**: inmobiliaria, gastronomía, automotriz, etc.
4. **Productos**: qué vende / ofrece
5. **Público objetivo**: cliente ideal, zonas, objeciones frecuentes
6. **Calificación BANT**: qué criterios querés que filtre el bot
7. **Agenda**: si usa Cal.com, horarios
8. **Comunicación**: tono del bot, emojis, idioma

Al final descarga un archivo `mi-empresa.yaml` y te lo manda por WhatsApp.

### 🚀 Paso 3 — Vos activás al cliente (1 comando, 30 segundos)

Vos (o Arnaldo) corre:
```bash
python onboard_mica_cliente.py mi-empresa.yaml
```

El script automáticamente:
- Valida los datos
- Crea la instancia de WhatsApp del cliente
- Registra al cliente en tu Airtable
- **Te genera este mensaje listo para copiar y pegar**:

```
¡Hola Juan! 👋

Ya tenemos lista tu integración de Inmobiliaria García con System IA.

Para activar tu bot de WhatsApp solo tenés que:

1️⃣ Entrar a este link desde la PC o celular:
https://systemia-onboarding.vercel.app/?slug=inmobiliaria-garcia

2️⃣ Escanear el código QR con el WhatsApp Business que vas a usar para el bot
   (desde tu celular: menú → Dispositivos vinculados → Vincular nuevo)

3️⃣ Listo. La página te muestra automáticamente:
 • Link a tu CRM (donde vas a ver todos tus leads y propiedades)
 • Link a Chatwoot (para atender manualmente cuando haga falta)

— Micaela | System IA
```

### 📱 Paso 4 — Cliente se conecta solo (1 minuto)

El cliente:
1. Entra al link que le mandaste
2. Ve el nombre de su empresa precargado
3. Escanea el QR con su WhatsApp Business
4. La página detecta la conexión y le muestra sus links (CRM, Chatwoot)

**Listo. El bot empieza a responder en su WhatsApp.**

---

## 💸 Qué vende Mica — propuesta de valor clara

Cuando hables con un prospecto, le estás ofreciendo:

### 🤖 1. Bot WhatsApp con IA (el producto estrella)
- Responde 24/7 sin intervención humana
- Conversacional de verdad (GPT-4.1-mini, no guiones rígidos)
- Califica leads con metodología BANT (Budget, Authority, Need, Timeline)
- Agenda citas automáticamente con Cal.com
- Maneja objeciones, muestra propiedades/productos, envía fotos
- Transcribe audios del cliente automáticamente
- Pausa solo si un humano toma la conversación en Chatwoot

### 📊 2. CRM visual con IA integrada
- Ve todos los leads en tiempo real
- Filtros por zona, tipo, operación, presupuesto
- Métricas: cuántos leads por mes, cuántas citas agendadas, tasa de conversión
- **Chat de IA integrado**: le podés preguntar "¿cuántos leads vinieron de Posadas este mes?" y te responde

### 💬 3. Chatwoot (atención humana híbrida)
- Cuando el bot detecta que el cliente quiere hablar con un humano, pausa el bot
- El asesor responde desde Chatwoot (web o app móvil)
- Todo el historial queda guardado
- Cuando el asesor termina, puede reactivar el bot

### 📅 4. Integración Cal.com (opcional)
- El bot muestra horarios disponibles
- Confirma citas sin que nadie tenga que hacer nada
- Se integra con el calendario del asesor

### 🔔 5. Notificaciones a Telegram (opcional)
- Cada lead calificado llega al Telegram del asesor
- El asesor ve todo el contexto de la conversación + score de calidad

---

## 🎨 ¿Cómo usar todo esto para vender?

### Para la primera reunión con un prospecto:
1. Mostrale el bot demo escribiéndole desde tu celular al número Demos
2. Mostrale el CRM y el chat de IA
3. Preguntale: "¿Tu negocio tiene WhatsApp para ventas? ¿Cuántos leads recibís por día que no alcanzás a responder?"
4. Explicale que esto es para dejar de perder leads por no atender a tiempo

### Para cerrar:
- Menciona que la implementación es de **menos de 1 día** una vez que complete el brief
- Que él mismo conecta su WhatsApp sin ayuda técnica
- Que puede cancelar cuando quiera (sin contratos largos al principio)

### Precios sugeridos (definilos vos según tu mercado):
- **Setup único**: $X (instalación + training de 1 hora)
- **Mensual**: $Y (incluye bot, CRM, Chatwoot, soporte, OpenAI incluido en el plan Arnaldo)

---

## 🚨 Cosas importantes que tenés que saber

### ✅ Lo que funciona sin problema
- Bot respondiendo 24/7
- CRM sincronizado con Airtable
- Chatwoot para humanos
- Demo inmobiliaria probada end-to-end

### ⚠️ Limitaciones actuales (no bloqueantes)
1. **Cada cliente nuevo requiere que Arnaldo corra un comando** — no es 100% self-service todavía. Próxima fase: form que provisiona solo.
2. **El cliente conecta con QR** — hasta que Robert sea aprobado como Tech Provider (2-10 días más). Después será login oficial con Meta.
3. **Crear inbox Chatwoot es manual** — tarda 2 minutos. Próxima fase: automático.

### 🛡️ Sobre riesgo de baneo de WhatsApp (IMPORTANTE que lo sepa tu cliente)
- Estamos usando **Evolution API** (no oficial pero muy usado en la industria)
- Riesgo de baneo existe pero es **bajo si se usa bien**:
  - No enviar masivamente a contactos que no iniciaron conversación
  - No usar un número personal de WhatsApp (mejor crear uno nuevo solo para el bot)
  - El bot responde SOLO a mensajes entrantes (no envía primero)
- Cuando Robert sea aprobado, migramos a Tech Provider Meta oficial y **desaparece el riesgo**.

---

## 📦 Stack técnico (para que sepas qué decir si te preguntan)

No hace falta que lo entiendas, solo que lo tengas a mano:

| Capa | Qué usamos |
|---|---|
| WhatsApp | Evolution API (self-hosted en Easypanel) |
| Bot | Python (FastAPI), en un contenedor en Coolify |
| IA conversacional | GPT-4.1-mini de OpenAI |
| Base de datos | Airtable (base `appA8QxIhBYYAHw0F`) |
| CRM visual | HTML + Tailwind en Vercel |
| Chatwoot | Tu instancia (compartida con Arnaldo por ahora) |
| Agenda | Cal.com |
| Automatizaciones | n8n |
| Auditoría 24/7 | Scripts Python que corren cada mañana y alertan por Telegram si algo falla |

---

## 🗓️ Roadmap futuro (lo que viene)

### Semana próxima (fase 2C)
- [ ] Chatwoot auto-provision (crear inbox automático al activar cliente nuevo)
- [ ] Auditor específico de ecosistema Mica (alertas dedicadas)
- [ ] Form dual: cuando Robert sea aprobado, el mismo form detecta si el cliente va por Evolution o Tech Provider

### Cuando aprueben a Robert (en 2-10 días)
- [ ] Migrar clientes Mica existentes a Tech Provider Meta (opcional, no obligatorio)
- [ ] Clientes nuevos van directo a Tech Provider
- [ ] Desaparece el paso del QR — login oficial Meta en 1 click

### Mediano plazo (1-3 meses)
- [ ] Mica se registra como Tech Provider propio (independiente de Robert) — opcional
- [ ] Plantillas de bot por vertical (inmobiliaria, gastronomía, automotriz, salud)
- [ ] Dashboard agencia: Mica ve todos sus clientes en un solo panel
- [ ] Facturación automatizada por cliente

### Largo plazo (6-12 meses)
- [ ] Expansión a otros países de LATAM
- [ ] Marketplace de plantillas que otros puedan usar
- [ ] App móvil propia de Mica para gestionar sus clientes

---

## 📞 ¿Qué hacés ahora?

**Opción 1 — Probar el flujo completo con un cliente ficticio**:
Hablá con Arnaldo, inventen un cliente de prueba, completen el brief, provisionen y vean los links funcionando.

**Opción 2 — Mandar el link del brief a tu primer prospecto real**:
El sistema ya está listo. Si tenés un cliente interesado, mandale `systemia-brief-form.vercel.app` y arrancá.

**Opción 3 — Armar la demo de ventas**:
Grabá un video de 5 minutos con tu celular mostrando el bot + CRM + Chatwoot. Sube a un link público. Usalo en todas tus primeras reuniones.

---

## 🆘 Contacto técnico

- **Arnaldo** — socio técnico, cualquier duda o problema
- **Documentación interna**: repo `Arnaldo999/system-ia-agentes`
- **Monitor automático**: Telegram (recibís alertas si algo falla)

---

_Este roadmap se actualiza cada vez que hay cambios. Última versión: 2026-04-20._
