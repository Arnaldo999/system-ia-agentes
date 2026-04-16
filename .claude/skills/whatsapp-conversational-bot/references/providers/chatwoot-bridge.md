# Chatwoot Bridge — Integración multi-proveedor

Chatwoot es el **CRM de conversaciones** que se integra sobre CUALQUIER proveedor WhatsApp. Permite que un asesor humano tome control de la conversación desde una UI.

Usado en el ecosistema Arnaldo/Lovbot: `chatwoot.arnaldoayalaestratega.cloud` (Coolify Hostinger) y `chatwoot.lovbot.ai` (Coolify Hetzner).

## Cuándo usar Chatwoot

- Cuando el cliente quiere que **asesores humanos** atiendan en ciertas conversaciones
- Cuando se necesita **dashboard de conversaciones** visual
- Cuando hay **múltiples asesores** que se reparten leads
- Cuando se quiere que el bot **pause** automáticamente cuando un humano interviene

## Arquitectura — Bridge FastAPI

El bot y Chatwoot comparten un mismo hilo de conversación vía el worker. FastAPI es el único camino que escribe a Chatwoot (no dejar que el proveedor WhatsApp escriba directo a Chatwoot).

```
┌────────────────┐
│ WhatsApp Meta/ │
│ Evolution/     │
│ YCloud webhook │
└───────┬────────┘
        ▼
┌──────────────────────┐
│ FastAPI worker        │
│ - Procesa con LLM     │──→ ┌──────────────┐
│ - Responde al cliente │    │ Chatwoot API │
│ - Publica en Chatwoot │──→ │ (mensajes +  │
│ - Escucha webhook     │◄── │ conversation)│
│   de Chatwoot         │    └──────────────┘
└──────────────────────┘
```

## Variables de entorno

```bash
# Chatwoot Arnaldo
CHATWOOT_URL=https://chatwoot.arnaldoayalaestratega.cloud
CHATWOOT_API_TOKEN=tu_token_de_user_o_agent_bot
CHATWOOT_ACCOUNT_ID=1
CHATWOOT_INBOX_ID=1

# Chatwoot Robert (Lovbot)
LOVBOT_CHATWOOT_URL=https://chatwoot.lovbot.ai
LOVBOT_CHATWOOT_API_TOKEN=xxx
LOVBOT_CHATWOOT_ACCOUNT_ID=2
LOVBOT_CHATWOOT_INBOX_ID=4
```

## Publicar mensajes en Chatwoot

Cada mensaje que recibe/envía el bot se publica en Chatwoot como `message_type: incoming` (del cliente) o `outgoing` (del bot):

```python
def _chatwoot_find_or_create_conversation(telefono: str, nombre: str = "") -> int | None:
    """Busca o crea una conversación en Chatwoot. Devuelve conversation_id."""
    # 1) Buscar contacto por phone_number
    r = requests.get(
        f"{CHATWOOT_URL}/api/v1/accounts/{CHATWOOT_ACCOUNT_ID}/contacts/search",
        headers={"api_access_token": CHATWOOT_API_TOKEN},
        params={"q": telefono, "include": "contact_inboxes"},
        timeout=8
    )
    contact_id = None
    if r.status_code == 200 and r.json().get("payload"):
        contact_id = r.json()["payload"][0]["id"]
    else:
        # Crear contacto
        r2 = requests.post(
            f"{CHATWOOT_URL}/api/v1/accounts/{CHATWOOT_ACCOUNT_ID}/contacts",
            headers={"api_access_token": CHATWOOT_API_TOKEN, "Content-Type": "application/json"},
            json={
                "inbox_id": CHATWOOT_INBOX_ID,
                "name": nombre or telefono,
                "phone_number": f"+{telefono}",
                "identifier": telefono,
            },
            timeout=8
        )
        if r2.status_code in (200, 201):
            contact_id = r2.json().get("payload", {}).get("contact", {}).get("id")

    if not contact_id:
        return None

    # 2) Buscar conversación abierta
    r3 = requests.get(
        f"{CHATWOOT_URL}/api/v1/accounts/{CHATWOOT_ACCOUNT_ID}/contacts/{contact_id}/conversations",
        headers={"api_access_token": CHATWOOT_API_TOKEN},
        timeout=8
    )
    if r3.status_code == 200:
        convs = r3.json().get("payload", [])
        abiertas = [c for c in convs if c.get("status") != "resolved"]
        if abiertas:
            return abiertas[0]["id"]

    # 3) Crear conversación nueva
    r4 = requests.post(
        f"{CHATWOOT_URL}/api/v1/accounts/{CHATWOOT_ACCOUNT_ID}/conversations",
        headers={"api_access_token": CHATWOOT_API_TOKEN, "Content-Type": "application/json"},
        json={"source_id": telefono, "inbox_id": CHATWOOT_INBOX_ID, "contact_id": contact_id},
        timeout=8
    )
    if r4.status_code in (200, 201):
        return r4.json().get("id")
    return None


def _chatwoot_publicar_mensaje(conversation_id: int, contenido: str, es_del_bot: bool = False) -> bool:
    """Publica un mensaje en Chatwoot."""
    r = requests.post(
        f"{CHATWOOT_URL}/api/v1/accounts/{CHATWOOT_ACCOUNT_ID}/conversations/{conversation_id}/messages",
        headers={"api_access_token": CHATWOOT_API_TOKEN, "Content-Type": "application/json"},
        json={
            "content": contenido,
            "message_type": "outgoing" if es_del_bot else "incoming",
            "private": False,
        },
        timeout=8
    )
    return r.status_code in (200, 201)
```

## Pausar el bot cuando un humano toma la conversación

El worker mantiene un diccionario en memoria `BOT_PAUSADO` con los teléfonos donde un asesor está activo:

```python
BOT_PAUSADO: set[str] = set()

def pausar_bot(telefono: str):
    BOT_PAUSADO.add(telefono)
    print(f"[BOT-PAUSE] {telefono}")

def reanudar_bot(telefono: str):
    BOT_PAUSADO.discard(telefono)

def bot_pausado(telefono: str) -> bool:
    return telefono in BOT_PAUSADO
```

En `_procesar()`:
```python
def _procesar(telefono: str, texto: str, referral: dict = None) -> None:
    if bot_pausado(telefono):
        print(f"[BOT] Pausado para {telefono} — asesor activo")
        return
    # ... resto del procesamiento
```

## Webhook de Chatwoot → FastAPI

Chatwoot puede mandar eventos al FastAPI cuando un agente toma la conversación. Configurar en Chatwoot → Settings → Integrations → Webhooks:

```python
@router.post("/webhook/chatwoot")
async def webhook_chatwoot(request: Request):
    payload = await request.json()
    event = payload.get("event", "")

    if event == "message_created":
        # Un agente humano mandó un mensaje → pausar bot
        msg = payload.get("content", "")
        sender_type = payload.get("sender", {}).get("type", "")  # "User" = agente humano
        msg_type = payload.get("message_type", "")

        conv = payload.get("conversation", {})
        telefono = conv.get("meta", {}).get("sender", {}).get("identifier", "")

        if sender_type == "User" and msg_type == "outgoing" and telefono:
            # Agente humano está respondiendo → pausar bot y reenviar al cliente
            pausar_bot(telefono)
            _enviar_texto(telefono, msg)

    elif event == "conversation_resolved":
        telefono = payload.get("meta", {}).get("sender", {}).get("identifier", "")
        if telefono:
            reanudar_bot(telefono)

    elif event == "conversation_updated":
        # Score label cambió → sincronizar con CRM/PostgreSQL
        labels = payload.get("labels", [])
        telefono = payload.get("meta", {}).get("sender", {}).get("identifier", "")
        score = None
        for l in labels:
            if l in ("caliente", "tibio", "frio"):
                score = l
        if telefono and score:
            _sincronizar_score_crm(telefono, score)

    return {"status": "ok"}
```

## Escalar a asesor (ir_asesor)

Cuando el bot decide escalar, publica nota privada para el asesor y pausa el bot:

```python
def _chatwoot_escalar(telefono: str, sesion: dict, calificacion: dict):
    conv_id = _chatwoot_find_or_create_conversation(telefono, sesion.get("nombre", ""))
    if not conv_id:
        return

    nota = f"""🔔 *LEAD PARA ATENDER*
Score: {calificacion.get('score', 'tibio')}
Tipo: {calificacion.get('tipo', 'n/a')}
Zona: {calificacion.get('zona', 'n/a')}
Presupuesto: {sesion.get('resp_presupuesto', 'n/a')}
Urgencia: {sesion.get('resp_urgencia', 'n/a')}

Nota: {calificacion.get('nota_para_asesor', '')}"""

    # Publicar como nota privada (solo ven los agentes)
    requests.post(
        f"{CHATWOOT_URL}/api/v1/accounts/{CHATWOOT_ACCOUNT_ID}/conversations/{conv_id}/messages",
        headers={"api_access_token": CHATWOOT_API_TOKEN, "Content-Type": "application/json"},
        json={"content": nota, "message_type": "outgoing", "private": True},
        timeout=8
    )

    # Agregar label
    requests.post(
        f"{CHATWOOT_URL}/api/v1/accounts/{CHATWOOT_ACCOUNT_ID}/conversations/{conv_id}/labels",
        headers={"api_access_token": CHATWOOT_API_TOKEN, "Content-Type": "application/json"},
        json={"labels": [calificacion.get('score', 'tibio')]},
        timeout=8
    )

    # Asignar a un asesor específico (opcional)
    if NOMBRE_ASESOR_USER_ID:
        requests.post(
            f"{CHATWOOT_URL}/api/v1/accounts/{CHATWOOT_ACCOUNT_ID}/conversations/{conv_id}/assignments",
            headers={"api_access_token": CHATWOOT_API_TOKEN, "Content-Type": "application/json"},
            json={"assignee_id": NOMBRE_ASESOR_USER_ID},
            timeout=8
        )
```

## Inboxes por cliente (importante)

Cada cliente debe tener **su propio inbox** en Chatwoot. Nunca compartir inboxes entre clientes. Razones:
- Separación de asesores que pueden ver
- Métricas por cliente
- Avoid data leaking

Inbox IDs actuales:
- **Arnaldo prueba**: `CHATWOOT_INBOX_ID=1` en chatwoot.arnaldoayalaestratega.cloud
- **Maicol**: `CHATWOOT_INBOX_ID=2` en chatwoot.arnaldoayalaestratega.cloud
- **Robert**: `LOVBOT_CHATWOOT_INBOX_ID=4` en chatwoot.lovbot.ai
