# Deploy + Test Loop — Coolify + curl + admin endpoints

Ciclo deterministic para deployar worker y validarlo en < 2 minutos. Funciona igual para Robert (Coolify Hetzner), Mica/Maicol (Coolify Hostinger) y otros clientes.

## 1. Commit + push

```bash
cd "/home/arna/PROYECTOS SYSTEM IA/SYSTEM_IA_MISSION_CONTROL"

# Validar sintaxis ANTES de commit
cd 01_PROYECTOS/01_ARNALDO_AGENCIA/backends/system-ia-agentes
python3 -m py_compile workers/clientes/lovbot/robert_inmobiliaria/worker.py && echo "OK sintaxis"
cd -

# Commit
git add "01_PROYECTOS/01_ARNALDO_AGENCIA/backends/system-ia-agentes/workers/..."
git commit -m "fix(robert-bot): descripción corta del cambio

Detalle:
- punto 1
- punto 2"

# Push (repo tiene master → main mapping)
git push origin master:main
```

## 2. Trigger deploy en Coolify

### Coolify Hetzner (Robert/Lovbot)

```bash
COOLIFY_TOKEN="1|ltGnDDHKbFeXRUcLgZ1GZ7t5EoifWyk1PZMvG3r0f41a7bd8"  # COOLIFY_ROBERT_TOKEN
APP_UUID="ywg48w0gswwk0skokow48o8k"  # system-ia-agentes

curl -s -X POST \
  -H "Authorization: Bearer $COOLIFY_TOKEN" \
  "https://coolify.lovbot.ai/api/v1/deploy?uuid=$APP_UUID&force=false" | \
  python3 -c "import json,sys; d=json.load(sys.stdin); print(d['deployments'][0]['deployment_uuid'])"
```

### Coolify Hostinger (Arnaldo/Maicol/Mica)

```bash
COOLIFY_TOKEN="$ARNALDO_COOLIFY_TOKEN"  # en .env
APP_UUID="ygjvl9byac1x99laqj4ky1b5"     # system-ia-agentes Arnaldo

curl -s -X POST \
  -H "Authorization: Bearer $COOLIFY_TOKEN" \
  "https://coolify.arnaldoayalaestratega.cloud/api/v1/deploy?uuid=$APP_UUID&force=false"
```

## 3. Esperar a que termine el deploy

```bash
DEPLOY_UUID="vk88kwkwk4k004skgso4ocwk"  # del step anterior

until curl -s -H "Authorization: Bearer $COOLIFY_TOKEN" \
  "https://coolify.lovbot.ai/api/v1/deployments/$DEPLOY_UUID" | \
  python3 -c "import json,sys; d=json.load(sys.stdin); exit(0 if d.get('status')=='finished' else 1)" 2>/dev/null; \
do sleep 8; done && echo "Deploy listo"
```

## 4. Admin endpoints — obligatorios en cada worker

Para que sea posible testear sin hablar por WhatsApp real, cada worker debe tener estos endpoints:

```python
@router.post("/admin/reset-sesion/{telefono}")
def reset_sesion_bot(telefono: str):
    """Borra sesión + historial (RAM + DB)."""
    tel = re.sub(r'\D', '', telefono)
    SESIONES.pop(tel, None)
    HISTORIAL.pop(tel, None)
    if USE_POSTGRES:
        try:
            db.delete_bot_session(tel)
        except Exception:
            pass
    return {"status": "ok", "telefono": tel, "mensaje": "Sesión borrada"}


@router.post("/admin/simular-lead-anuncio/{telefono}")
async def simular_lead_anuncio(telefono: str, request: Request):
    """Simula lead desde anuncio Meta Ads (testing Caso A)."""
    tel = re.sub(r'\D', '', telefono)
    body = await request.json()
    referral = {
        "headline": body.get("headline", "Casa en San Ignacio"),
        "body": body.get("body", ""),
        "source_url": body.get("source_url", "fb.com/ad/123"),
    }
    nombre_ads = body.get("nombre", "").strip()
    email_ads = body.get("email", "").strip()
    if nombre_ads or email_ads:
        sesion_pre = SESIONES.get(tel, {})
        if nombre_ads: sesion_pre["nombre"] = nombre_ads.title()
        if email_ads: sesion_pre["email"] = email_ads
        sesion_pre["origen_lead"] = "meta_ads_form"
        SESIONES[tel] = sesion_pre

    primer_mensaje = body.get("mensaje", "Hola, me interesa lo del aviso")
    threading.Thread(target=_procesar, args=(tel, primer_mensaje, referral), daemon=True).start()
    return {"status": "processing", "telefono": tel, "referral": referral}


@router.get("/admin/ver-sesion/{telefono}")
def ver_sesion_bot(telefono: str):
    """Devuelve estado actual de la sesión para testing."""
    tel = re.sub(r'\D', '', telefono)
    return {
        "telefono": tel,
        "sesion": SESIONES.get(tel, {}),
        "historial_ultimos_10": HISTORIAL.get(tel, [])[-10:],
        "en_memoria": tel in SESIONES,
    }
```

## 5. Ciclo de test completo

```bash
BASE="https://agentes.lovbot.ai/clientes/lovbot/inmobiliaria"
TEL="5493765384843"

# Step 1: reset
curl -s -X POST "$BASE/admin/reset-sesion/$TEL" && echo ""

# Step 2: simular lead Caso A (desde anuncio)
curl -s -X POST "$BASE/admin/simular-lead-anuncio/$TEL" \
  -H "Content-Type: application/json" \
  -d '{
    "headline":"Lote en country San Ignacio - USD 18k",
    "body":"600m2 con escritura inmediata",
    "nombre":"Arnaldo Ayala",
    "mensaje":"Hola, vi tu publicación, sigue disponible?"
  }'

# Step 3: esperar respuesta del bot
until curl -s "$BASE/admin/ver-sesion/$TEL" | \
  python3 -c "import json,sys; d=json.load(sys.stdin); exit(0 if [h for h in d['historial_ultimos_10'] if 'Bot:' in h] else 1)" 2>/dev/null; \
do sleep 2; done

# Step 4: ver qué dijo el bot
curl -s "$BASE/admin/ver-sesion/$TEL" | python3 -c "
import json, sys
d = json.load(sys.stdin)
print('Step:', d['sesion'].get('step'))
print('--- Historial ---')
for h in d['historial_ultimos_10']: print(h[:200])
"

# Step 5: enviar mensaje del cliente via webhook (como si fuera Meta real)
curl -s -X POST "$BASE/whatsapp" \
  -H "Content-Type: application/json" \
  -d "{
    \"object\":\"whatsapp_business_account\",
    \"entry\":[{
      \"id\":\"1\",
      \"changes\":[{
        \"value\":{
          \"messaging_product\":\"whatsapp\",
          \"metadata\":{\"display_phone_number\":\"x\",\"phone_number_id\":\"y\"},
          \"contacts\":[{\"profile\":{\"name\":\"Arnaldo\"},\"wa_id\":\"$TEL\"}],
          \"messages\":[{
            \"from\":\"$TEL\",
            \"id\":\"wamid.test$(date +%s)\",
            \"timestamp\":\"$(date +%s)\",
            \"type\":\"text\",
            \"text\":{\"body\":\"que opciones tienen para inversion\"}
          }]
        },
        \"field\":\"messages\"
      }]
    }]
  }"
```

## 6. Caso B — Lead genérico (sin referral)

```bash
# Step 1: reset
curl -s -X POST "$BASE/admin/reset-sesion/$TEL"

# Step 2: enviar mensaje directo via webhook (sin referral)
curl -s -X POST "$BASE/whatsapp" \
  -H "Content-Type: application/json" \
  -d "{
    \"object\":\"whatsapp_business_account\",
    \"entry\":[{
      \"changes\":[{
        \"value\":{
          \"messaging_product\":\"whatsapp\",
          \"contacts\":[{\"profile\":{\"name\":\"Arnaldo\"},\"wa_id\":\"$TEL\"}],
          \"messages\":[{
            \"from\":\"$TEL\",
            \"id\":\"wamid.t1\",
            \"type\":\"text\",
            \"text\":{\"body\":\"Hola, vi sus propiedades\"}
          }]
        },\"field\":\"messages\"
      }]
    }]
  }"
```

## 7. Limitaciones del test cycle

El test **no verifica**:
- Que el mensaje llegue a WhatsApp real (porque estamos simulando, no enviando a Meta)
- Validación de firma de webhook (si está activada)

El test **sí verifica**:
- Estado de sesión después de cada mensaje
- Historial de conversación en RAM
- Step actual del bot
- Datos BANT extraídos
- ACCION elegida (mostrar_props, ir_asesor, etc.)

## 8. Debug: ver logs en Coolify

```bash
# Robert
curl -s -H "Authorization: Bearer $COOLIFY_TOKEN" \
  "https://coolify.lovbot.ai/api/v1/applications/$APP_UUID/logs?lines=100" | \
  python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('logs','')[-3000:])"
```

O usando el MCP `plugin_vercel_vercel__deployment-expert` si es Vercel.

## 9. Rollback si algo falla

```bash
# Coolify no tiene rollback 1-click, hay que deployar un commit anterior:
cd "/home/arna/PROYECTOS SYSTEM IA/SYSTEM_IA_MISSION_CONTROL"
git log --oneline -10  # ver últimos commits
git revert <hash-malo>
git push origin master:main
# → auto-deploy en Coolify
```

## 10. Checklist pre-deploy

Antes de cada deploy, verificar:

- [ ] `python3 -m py_compile worker.py` sin errores
- [ ] Cambios probados en worker `demos/` antes de copiarlos a `clientes/`
- [ ] Commit con mensaje descriptivo
- [ ] No hay API keys en el código (buscar con grep)
- [ ] Si cambiaste env vars, actualizar en Coolify panel antes del deploy
- [ ] Si el cambio es crítico, avisar al usuario antes de deployar (bot en prod)

## 11. Tabla de URLs y UUIDs por proyecto

| Proyecto | Backend URL | Coolify App UUID | Coolify Host |
|---|---|---|---|
| Robert/Lovbot | `agentes.lovbot.ai` | `ywg48w0gswwk0skokow48o8k` | `coolify.lovbot.ai` (Hetzner) |
| Arnaldo/Maicol | `agentes.arnaldoayalaestratega.cloud` | `ygjvl9byac1x99laqj4ky1b5` | `coolify.arnaldoayalaestratega.cloud` (Hostinger) |
| Mica demo | idem Arnaldo (compartido) | idem | idem |

## 12. Ejecución automatizada con script

Ver `scripts/test-bot.sh` para un flujo completo preempaquetado:

```bash
./scripts/test-bot.sh <cliente> <numero> <caso_a|caso_b>
# Ejemplos:
./scripts/test-bot.sh robert 5493765384843 caso_a
./scripts/test-bot.sh mica 5493765005465 caso_b
./scripts/test-bot.sh maicol 5493764815689 caso_a
```
