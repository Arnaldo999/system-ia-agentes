# Handoff Robert — Bot de voz Lovbot Inmobiliaria

> Documento ejecutable por Robert (o por nosotros en su lugar) para
> pasar el bot de voz desde la cuenta de Arnaldo (ElevenCreative) a la
> cuenta propia de Robert + número Twilio AR.

**Contenido de esta carpeta**:
- `system-prompt.md` — pegar en ElevenLabs UI campo "System Prompt"
- `tools.json` — 5 custom tools para crear en ElevenLabs
- `kb-faq-inmobiliaria.md` — subir como Knowledge Base doc 1
- `kb-planes-y-servicios.md` — subir como Knowledge Base doc 2

---

## Estado actual (al 2026-04-27)

| Pieza | Estado | Dónde |
|-------|--------|-------|
| Backend FastAPI con 5 endpoints `/voz/*` | ✅ Codeado, pendiente deploy | `workers/demos/inmobiliaria_voz/worker.py` |
| Módulos shared (calcom_client, catalog, lead_matcher, bant) | ✅ Codeado, pendiente deploy | `workers/shared/*.py` |
| Routing en main.py | ✅ Listo | `prefix=/demos/voz/inmobiliaria` |
| URL pública | ⏳ Después de deploy | `https://agentes.lovbot.ai/demos/voz/inmobiliaria/*` |
| Agente ElevenLabs configurado | ⏳ Pendiente — pasos 1-5 abajo | Cuenta ElevenCreative (Arnaldo) durante dev |
| Número Twilio AR | ⏳ Pendiente — paso 6 abajo | Lo compra Robert con KYC propio |
| Conexión Twilio ↔ ElevenLabs | ⏳ Pendiente — paso 7 abajo | UI ElevenLabs |

---

## Costos esperados (mensual, asume Robert)

| Servicio | Plan recomendado | USD/mes |
|----------|------------------|---------|
| ElevenLabs Conversational AI | Creator | 22 |
| Twilio número AR | Tier voice | 1-3 |
| Twilio uso entrante | $0.04 / minuto | variable |
| Coolify Hetzner | sin costo extra | 0 |
| Postgres + Cal.com | sin costo extra | 0 |
| **Setup mínimo** |  | **~25 USD/mes + uso** |

Si supera 250 minutos/mes de conversación → escalar ElevenLabs a Pro
(USD 99/mes).

---

## Paso 1 — Deploy del backend (Arnaldo, 1 vez)

Antes de configurar ElevenLabs, los endpoints `/voz/*` tienen que estar
LIVE en `agentes.lovbot.ai`.

```bash
# Desde el repo system-ia-agentes
git add workers/shared/calcom_client.py workers/shared/catalog.py \
        workers/shared/lead_matcher.py workers/shared/bant.py \
        workers/demos/inmobiliaria_voz/ main.py
git commit -m "feat(voz): worker demo voz inmobiliaria + shared modules"
git push origin master:main

# Trigger redeploy en Coolify Hetzner Robert (mismo service que ya
# corre el WhatsApp). Verificar:
curl https://agentes.lovbot.ai/demos/voz/inmobiliaria/healthz
# → {"ok":true,"service":"voz-demo-inmobiliaria","calcom_configured":true,...}
```

Si `calcom_configured: false` → faltan env vars `INMO_DEMO_CAL_*` en Coolify.

---

## Paso 2 — Crear el agente en ElevenLabs (Arnaldo durante dev)

1. Ir a https://elevenlabs.io/app/agents
2. New Agent → "Business Agent" → "Real Estate" → "Scheduling"
3. Nombre: **Lovbot Inmobiliaria — Voz (Dev)**
4. Idioma principal: **Español**
5. Additional languages: **English** (toggle "auto-detect" ON)

---

## Paso 3 — Configurar System Prompt + Modelo + Voz

| Campo | Valor |
|-------|-------|
| System Prompt | Pegar contenido de `system-prompt.md` |
| LLM | **Gemini 2.5 Flash** |
| Temperature | **0.5** |
| Token limit | **-1** (ilimitado) |
| Voice ID | `16UXUey4OpoKrC9IiRNt` (la elegida por Arnaldo) |
| Greeting message | "Hola, soy el asistente de Lovbot Inmobiliaria, ¿en qué puedo ayudarte?" |

Configuraciones avanzadas:
- Turn timeout: **7 segundos**
- Silence call timeout: **60 segundos**
- Max conversation: **600 segundos** (10 min)

---

## Paso 4 — Subir Knowledge Base

En la sección "Knowledge Base" del agente, subir 2 documentos:

1. `kb-faq-inmobiliaria.md` (renombrar a `.md` o pegar como text)
2. `kb-planes-y-servicios.md`

ElevenLabs avisa que "tu knowledge base es lo suficientemente pequeña
para incluirla directamente en el prompt" — eso está bien, NO usar RAG
en este caso.

---

## Paso 5 — Crear las 5 Custom Tools

Para cada tool de `tools.json`:

1. Tools → Add Custom Tool → "Edit as JSON"
2. Pegar el bloque correspondiente del array `tools[]`
3. Verificar:
   - URL apunta a `https://agentes.lovbot.ai/demos/voz/inmobiliaria/...`
   - Response timeout: **40 segundos**
   - Pre-tool speech: "Un momento, lo verifico."
   - Body parameters mapean correctamente (`dynamic_variable` o `llm_prompt`)
4. Guardar

Las 5 tools son:
- `identificar_lead`
- `buscar_propiedad`
- `disponibilidad`
- `agendar_visita`
- `cancelar_visita`

---

## Paso 6 — Test desde "Test AI agent" (sin número aún)

Antes de comprar Twilio, validar el agente con el botón "Test AI agent"
del dashboard ElevenLabs:

Casos a probar (mínimo 5):

- [ ] **Saludo**: el agente saluda en español argentino, voz natural
- [ ] **Identificar lead nuevo**: el agente llama `identificar_lead` y
  reconoce que es nuevo
- [ ] **Búsqueda**: pedirle "quiero una casa en zona sur por 80 mil
  dólares" → debe llamar `buscar_propiedad`
- [ ] **Agendamiento**: "quiero visitar mañana a las 10" → llama
  `disponibilidad` → ofrece slots reales → confirma uno → pide nombre
  + email letra por letra → llama `agendar_visita` → confirma
- [ ] **Verificar en Cal.com**: el booking aparece en la cuenta de
  Arnaldo Cal.com con metadata `canal: voz`
- [ ] **Verificar en Postgres**: el lead aparece en `leads` con
  `fuente_detalle = "canal:voz"`

Si todo OK → seguir paso 7. Si algo falla, debug usando los logs de
Coolify Hetzner.

---

## Paso 7 — Robert paga ElevenLabs y compra Twilio

**Cuándo hacer este paso**: cuando el demo esté validado y Robert quiera
pasarlo a producción con número real.

### 7a. Robert crea cuenta ElevenLabs

- https://elevenlabs.io → sign up
- Plan **Creator** (USD 22/mes) — alcanza para ~250 min de conversación
- Anotar API Key (se necesita después)

### 7b. Importar el agente en cuenta Robert

Opciones:
1. **Manual**: replicar pasos 2-5 en cuenta Robert (recomendado, da
   control total).
2. **Vía API** (si ElevenLabs habilita export/import oficial — verificar
   feature al momento del handoff).

Resultado: nuevo `agent_id` en cuenta Robert.

### 7c. Robert compra número Twilio AR

- https://www.twilio.com → sign up
- Console → Phone Numbers → Buy a number
- País: **Argentina**
- Capabilities: **Voice** (mínimo)
- KYC AR: subir DNI/CUIT + comprobante domicilio + justificación uso
- **Tiempo de aprobación: 3-10 días hábiles**

### 7d. Conectar Twilio ↔ ElevenLabs

En ElevenLabs:
- Agent → Phone Numbers → Add Number → Twilio
- Pegar Twilio Account SID + Auth Token
- Seleccionar el número comprado
- Verificar que el agente conteste al marcar el número

---

## Paso 8 — Actualizar env vars en Coolify (handoff técnico final)

En Coolify Hetzner Robert, agregar/actualizar:

```
LOVBOT_ELEVENLABS_API_KEY=<key de Robert>
LOVBOT_ELEVENLABS_AGENT_ID=<agent_id de Robert>
```

(Estas vars hoy NO son consumidas por el backend porque ElevenLabs habla
con nuestros endpoints sin requerir auth. Las dejamos guardadas por si
se agrega validación HMAC más adelante.)

---

## Paso 9 — Promover demo → cliente Robert

Cuando el demo esté maduro y Robert quiera tener su URL propia:

```bash
# Copiar carpeta demo a cliente
cp -r workers/demos/inmobiliaria_voz workers/clientes/lovbot/robert_voz
# Actualizar prefix del router a /clientes/lovbot/robert/voz
# Actualizar URLs de las tools en ElevenLabs
# Redeploy
```

**No es urgente** — el demo en `/demos/voz/inmobiliaria` puede correr
producción durante meses sin problema.

---

## Troubleshooting rápido

| Síntoma | Causa probable | Fix |
|---------|----------------|-----|
| Tool da timeout | Endpoint backend tarda >40s | Subir timeout a 60s o optimizar query |
| Voz se corta | Conexión inestable o `silence_call_timeout` muy bajo | Subir a 90s |
| Lee precios falsos | LLM inventando — system prompt no es claro | Reforzar regla "NEVER quote prices without buscar_propiedad" |
| Email mal deletreado | Modelo no usa Gemini 2.5 Flash | Cambiar LLM a Gemini 2.5 Flash |
| Slots vacíos | Cal.com sin INMO_DEMO_CAL_API_KEY | Agregar env var en Coolify |
| Lead no aparece en CRM | Postgres LOVBOT_PG_* mal configurado | Verificar healthz del worker WhatsApp también |
| Número Twilio rechazado | KYC AR pendiente | Esperar 3-10 días + responder mails Twilio |

---

## Si hace falta soporte en vivo durante el handoff

- Logs Coolify: https://coolify.lovbot.ai → service backend → Logs
- Logs ElevenLabs: dashboard agente → Conversations → cada llamada tiene transcript
- Postgres modelo: ver leads recientes
  ```sql
  SELECT telefono, nombre, score, fuente_detalle, fecha_ultimo_contacto
  FROM leads WHERE fuente_detalle LIKE 'canal:voz%'
  ORDER BY fecha_ultimo_contacto DESC LIMIT 10;
  ```
