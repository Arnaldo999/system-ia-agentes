# 📦 Paquete Meta App Review — Lovbot Tech Provider

App: `APP WorkFlow Whats Lovbot V2` (ID `704986485248523`)
Business: Lovbot Marketing
Permisos a solicitar:
- `whatsapp_business_management` → Advanced access
- `whatsapp_business_messaging` → Advanced access

---

## 🎯 PASO A PASO en Meta Developers

1. Abrí: https://developers.facebook.com/apps/704986485248523/app-review/permissions/
2. Buscá los 2 permisos en la lista
3. Clic en **"Solicitar acceso avanzado"** en cada uno
4. Llená lo que pide (copiá los textos de abajo)
5. Subí los 2 videos (después los grabás)
6. Submit

---

## 📝 JUSTIFICACIONES

### Para `whatsapp_business_management`

**Pregunta de Meta**: *"Describe cómo tu app utilizará este permiso"*

**Texto a copiar y pegar**:

```
Lovbot es una agencia de automatización con WhatsApp Business operando como
Tech Provider verificado de Meta. Utilizamos el permiso whatsapp_business_management
para gestionar los activos comerciales de WhatsApp de nuestros clientes (cuentas
de WhatsApp Business, números de teléfono, plantillas de mensajes y suscripciones
a webhooks).

Específicamente:
1. Cuando un cliente nuevo se registra en nuestra plataforma vía Embedded Signup,
   suscribimos su WhatsApp Business Account (WABA) a nuestra app para recibir los
   eventos de mensajes (POST a /{waba_id}/subscribed_apps).
2. Creamos y administramos plantillas de mensajes en nombre de nuestros clientes
   para campañas de re-engagement, recordatorios de citas y notificaciones
   transaccionales (GET/POST a /{waba_id}/message_templates).
3. Consultamos los números de teléfono asociados a cada WABA del cliente para
   configurar correctamente el routing de mensajes en nuestro backend
   (GET a /{waba_id}/phone_numbers).
4. Administramos la suscripción y desuscripción de webhooks por cliente para
   garantizar el correcto enrutamiento multi-tenant de eventos.

Todos los activos pertenecen al portafolio comercial del cliente final. Lovbot
solo opera en nombre del cliente con su autorización explícita otorgada durante
el flujo de Embedded Signup. Cada cliente mantiene control total sobre sus datos
y puede revocar el acceso en cualquier momento desde su Business Manager.
```

---

### Para `whatsapp_business_messaging`

**Pregunta de Meta**: *"Describe cómo tu app utilizará este permiso"*

**Texto a copiar y pegar**:

```
Lovbot utiliza el permiso whatsapp_business_messaging para enviar mensajes
de WhatsApp en nombre de nuestros clientes a través de la API en la nube de
WhatsApp Business. Esto permite que nuestros bots automatizados respondan a
los leads y clientes finales de cada negocio que contrata nuestros servicios.

Casos de uso específicos:
1. Respuesta automática a mensajes entrantes: cuando un lead escribe al WhatsApp
   Business de un cliente, nuestro bot procesa el mensaje con un modelo de IA
   y envía una respuesta inteligente vía POST a /{phone_number_id}/messages.
2. Envío de imágenes y archivos multimedia: cuando el lead solicita información
   de productos (propiedades, menú, catálogo), el bot envía las imágenes
   correspondientes con tipo "image" en la API.
3. Envío de plantillas pre-aprobadas para nurturing: a leads que completaron
   calificación pero no agendaron cita, enviamos plantillas de seguimiento a
   los 3, 15 y 30 días.
4. Confirmación de citas y notificaciones de actualización de estado.

Todos los mensajes se envían exclusivamente desde el número de WhatsApp Business
del cliente que nos otorgó el acceso vía Embedded Signup. Respetamos la ventana
de servicio al cliente de 24 horas y solo enviamos plantillas pre-aprobadas
fuera de esa ventana, en cumplimiento total con las políticas de Meta.

No usamos este permiso para mensajería no solicitada, spam, ni para fines
distintos a los servicios de automatización contratados por cada cliente.
```

---

## 🧪 INSTRUCCIONES PARA EL REVISOR DE META

**Pregunta de Meta**: *"Provide step-by-step instructions for our reviewers to test this functionality"*

**Texto a copiar y pegar**:

```
Test environment URL: https://lovbot-onboarding.vercel.app/?client=test-arnaldo

Step-by-step:

1. Open the URL above in a browser. You will see the Lovbot landing page with
   a "Conectar mi WhatsApp" button.

2. Click "Conectar mi WhatsApp" → Embedded Signup popup will open.

3. Sign in with your test Facebook account that has Business Manager access.

4. Select a verified business portfolio and connect a test WhatsApp Business
   Account (you can use Coexistence with an existing WhatsApp Business app).

5. After successful onboarding, our backend will automatically:
   - Exchange the OAuth code for a permanent access token
     (server-side call to graph.facebook.com/v21.0/oauth/access_token)
   - Subscribe the WABA to our app
     (POST to graph.facebook.com/v21.0/{waba_id}/subscribed_apps)
   - Store the tenant in our PostgreSQL database

6. To verify message reception works:
   Send any WhatsApp message from another number to the connected WhatsApp
   Business number.

7. The bot will automatically reply within 2-3 seconds with a test message
   confirming the full pipeline works end-to-end.

Production webhook URL: https://agentes.lovbot.ai/webhook/meta/events

Production verify token: contact arnaldo@lovbot.ai for test credentials

For technical questions: https://lovbot.mx (privacy policy and contact info available)
```

---

## 🎬 GUION VIDEO 1 — Envío de mensaje vía API (~2 minutos)

**Setup**:
- Pantalla compartida con: 1 navegador (Business Manager + WhatsApp Web abierto), 1 terminal con curl listo
- Sin cara, solo voz
- Idioma: español
- Calidad: 1080p mínimo

**Guion paso a paso** (lo que vas diciendo + lo que vas mostrando):

```
[0:00 - 0:15]  PRESENTACIÓN

VOZ: "Hola, soy el equipo de Lovbot, una agencia verificada como Tech Provider
de Meta. En este video voy a demostrar cómo enviamos mensajes de WhatsApp en
nombre de nuestros clientes usando el permiso whatsapp_business_messaging."

PANTALLA: Mostrá tu landing pública o el dashboard de Lovbot mientras hablás.


[0:15 - 0:45]  CONTEXTO TÉCNICO

VOZ: "Tenemos un backend en FastAPI corriendo en agentes.lovbot.ai que recibe
los webhooks de Meta y responde automáticamente a los mensajes de los leads
de cada cliente. Cada cliente tiene su propio número de WhatsApp Business
conectado vía Embedded Signup."

PANTALLA: Cambiá a tu Business Manager (business.facebook.com), entrá a WhatsApp
Manager y mostrá el número conectado del cliente que vas a usar de demo.


[0:45 - 1:30]  ENVÍO DEL MENSAJE

VOZ: "Voy a ejecutar una llamada a la API de Meta Graph para enviar un mensaje
de prueba. Esta es la misma llamada que ejecuta nuestro backend cuando un lead
escribe al cliente."

PANTALLA: Abrí la terminal y ejecutá el curl (ver más abajo). Pegalo y
ejecutalo.

VOZ: "El comando hace POST a graph.facebook.com versión 21 punto cero, al
endpoint del phone_number_id del cliente. Envía un mensaje de tipo texto al
número del lead."

PANTALLA: Mostrá la respuesta JSON exitosa de Meta (debe incluir message_id).


[1:30 - 1:55]  CONFIRMACIÓN EN WHATSAPP

PANTALLA: Cambiá a WhatsApp Web (o tu celular conectado) y mostrá el mensaje
recién enviado en el chat del destinatario.

VOZ: "Como pueden ver, el mensaje llegó al destinatario. Esto demuestra que
nuestra app utiliza correctamente el permiso whatsapp_business_messaging para
enviar mensajes en nombre del cliente, dentro de su ventana de servicio de
24 horas."


[1:55 - 2:00]  CIERRE

VOZ: "Gracias por la revisión. Para cualquier consulta técnica, contactanos
en arnaldo@lovbot.ai."
```

**Comando curl que vas a ejecutar en el video**:

```bash
# REEMPLAZÁ los valores antes de grabar:
#   {ACCESS_TOKEN}      = META_ACCESS_TOKEN del .env de Coolify
#   {PHONE_NUMBER_ID}   = 735319949657644 (Robert Bazan)
#   {DESTINATARIO}      = un nro de WhatsApp tuyo de prueba (formato: 5491130000000)

curl -X POST https://graph.facebook.com/v21.0/{PHONE_NUMBER_ID}/messages \
  -H "Authorization: Bearer {ACCESS_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "messaging_product": "whatsapp",
    "to": "{DESTINATARIO}",
    "type": "text",
    "text": {
      "body": "Hola! Este es un mensaje de prueba enviado desde el backend de Lovbot via Meta Graph API. Demostracion para revision de app de Meta."
    }
  }'
```

---

## 🎬 GUION VIDEO 2 — Creación de template (~2 minutos)

**Setup**: igual que Video 1 (pantalla + voz, sin cara)

**Guion paso a paso**:

```
[0:00 - 0:20]  PRESENTACIÓN

VOZ: "Continuando con la revisión de Lovbot, ahora voy a demostrar cómo creamos
plantillas de mensajes pre-aprobadas en nombre de nuestros clientes, usando el
permiso whatsapp_business_management."

PANTALLA: Business Manager → WhatsApp Manager.


[0:20 - 1:00]  NAVEGACIÓN A TEMPLATES

PANTALLA: Clic en "Plantillas de mensaje" en el menú izquierdo. Se ve la lista
de templates existentes (vas a crear uno nuevo).

VOZ: "Aquí están las plantillas que ya tenemos creadas para este cliente.
Vamos a crear una nueva plantilla de seguimiento que vamos a usar para hacer
nurturing de leads que no agendaron cita."

CLIC: Botón "Crear nueva plantilla".


[1:00 - 1:40]  CREACIÓN DEL TEMPLATE

PANTALLA: Llenás el formulario:
  - Categoría: Marketing
  - Nombre: nurturing_3_dias_demo
  - Idioma: Español (Argentina)
  - Cuerpo: "Hola {{1}}, soy el asistente de {{2}}. Vi que estuviste consultando
    propiedades en {{3}}. ¿Pudiste tomar una decisión? Si necesitás más info
    estoy acá 🏡"

VOZ: "Esta plantilla la usaremos para reactivar leads inactivos. Tiene 3
variables: nombre del lead, nombre del negocio, y zona de interés. Cumple con
las políticas de marketing de Meta."

CLIC: Enviar a aprobación.


[1:40 - 2:00]  CIERRE

PANTALLA: Mostrá la lista de plantillas con la nueva en estado "En revisión".

VOZ: "La plantilla queda en revisión de Meta. Una vez aprobada, podremos
enviarla via API a los leads que cumplan los criterios. Esto demuestra que
utilizamos el permiso whatsapp_business_management para crear y gestionar
templates en nombre del cliente. Gracias."
```

---

## 🛠 HERRAMIENTAS DE GRABACIÓN

**En Linux** (lo que usás):
- **OBS Studio** (recomendado, gratis, profesional): `sudo apt install obs-studio`
- **SimpleScreenRecorder** (más liviano): `sudo apt install simplescreenrecorder`
- **Vokoscreen** (más simple aún): `sudo apt install vokoscreen-ng`

**Configuración mínima**:
- Resolución: 1920x1080 (Full HD)
- FPS: 30
- Audio: micrófono encendido
- Formato salida: MP4 (H.264 + AAC)
- Bitrate video: 5000 Kbps mínimo

---

## ✅ CHECKLIST FINAL ANTES DE ENVIAR

Antes de hacer clic en "Enviar a revisión":

- [ ] App tiene política de privacidad pública (`https://lovbot.mx/politica-de-privacidad`) ✅
- [ ] App tiene términos de servicio publicados (FALTA — armar en lovbot.mx)
- [ ] App tiene URL de eliminación de datos publicada (FALTA — armar)
- [ ] Video 1 (envío mensaje) grabado, < 5 min, MP4
- [ ] Video 2 (template) grabado, < 5 min, MP4
- [ ] Justificaciones pegadas para los 2 permisos
- [ ] Instrucciones para revisor pegadas
- [ ] App tiene íconos de 1024x1024 subidos
- [ ] App tiene email de contacto del DPO (RGPD) si vas a operar en EU

---

## 📊 EXPECTATIVAS DE TIEMPO

| Tarea | Tiempo |
|---|---|
| Grabar 2 videos | 30 min (con tomas) |
| Editar y exportar videos | 15 min |
| Llenar formularios Meta | 15 min |
| Subir todo y enviar | 5 min |
| **TOTAL trabajo tuyo** | **~1h 5min** |
| Espera review Meta | 2-10 días hábiles |

---

## 🚨 SI META RECHAZA

Razones comunes de rechazo:
1. **Justificación genérica** → especificá MÁS qué hace tu app exactamente
2. **Video poco claro** → re-grabá mostrando más detalle de la API call
3. **Sin política de privacidad / términos** → completá esos URLs
4. **Plataforma de prueba inaccesible** → asegurate que la URL de prueba funcione cuando Meta la revise

Si rechaza, Meta te dice exactamente qué falta. Corregís y volvés a enviar (sin penalización por rechazo).
