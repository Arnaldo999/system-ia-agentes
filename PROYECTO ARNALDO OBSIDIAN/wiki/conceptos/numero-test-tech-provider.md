---
title: "Numero de test via Tech Provider Robert"
type: concepto
proyecto: compartido
tags: [tech-provider, testing, meta, whatsapp, wa-provider, aislamiento-entre-agencias]
---

# Numero de test unico via Tech Provider Robert

## Concepto

Un solo numero de WhatsApp conectado UNA VEZ al Tech Provider de [[lovbot-ai]] se usa como **sandbox compartido** para testear CUALQUIER worker del ecosistema (Arnaldo propio, Mica, Robert, demos de cualquier nicho) cambiando solo el `worker_url` en la tabla `waba_clients` — sin desconectar/reconectar de Meta.

Se aprovecha que [[robert-bazan]] es Tech Provider oficial de Meta (la unica de las 3 agencias que lo es), para que [[arnaldo-ayala]] (socio tecnico) obtenga numero WhatsApp oficial testeable sin depender de Evolution API de Mica o de YCloud.

## Problema que resuelve

Antes:
- Cada test requeria Evolution API de Mica o YCloud de Arnaldo (QR scan, desconexiones, bans).
- Los workers de Mica solo testeables contra Evolution, los de Arnaldo contra YCloud. Imposible testear multi-provider con el mismo numero.
- Para validar un worker desde vacio habia que setear credenciales de provider por agencia.

Despues:
- UN numero, siempre conectado, routeable a cualquier worker.
- El mismo payload Meta Graph llega al worker, independiente de para que agencia lo esten probando.
- Los workers demo quedan **provider-agnostic** — detectan formato del payload y usan el sender correspondiente.

## Arquitectura

```
Tu nro test (+54 9 X)
    │
    │ (conectado via Embedded Signup a la app Meta de Robert — UNA vez)
    ▼
Meta Graph
    │
    │ webhook fijo (no se puede cambiar por cliente)
    ▼
https://agentes.lovbot.ai/webhook/meta/events
    │
    │ backend Robert → webhook_meta.py (forwarder)
    │
    │ busca tenant por phone_number_id en PG waba_clients
    │
    ▼
worker_url ◄───────── CAMBIAS ESTO con probar_worker.sh
    │
    ├─► /clientes/arnaldo/demo-inmobiliaria/whatsapp  (demo Arnaldo)
    ├─► /clientes/system_ia/demos/inmobiliaria/whatsapp (demo Mica)
    ├─► /clientes/lovbot/robert_inmobiliaria/whatsapp (bot Robert)
    └─► https://ngrok-url/webhook (custom / externo)
```

## Componentes implementados (2026-04-20)

### 1. Modulo compartido `workers/shared/wa_provider.py`
Capa de abstraccion con 2 funciones principales:

- `send_text(telefono, mensaje, provider=None)` → envia via meta/evolution/ycloud segun `WHATSAPP_PROVIDER`.
- `parse_incoming(body)` → detecta formato del payload entrante (Meta Graph / Evolution / YCloud / bridge) y retorna dict unificado `{telefono, texto, nombre, tipo, provider, referral, raw}`.

### 2. Workers demo adaptados
Ambos demos inmobiliarios detectan `WHATSAPP_PROVIDER` en runtime:

- `workers/demos/inmobiliaria/worker.py` (Arnaldo) — default YCloud. Si `WHATSAPP_PROVIDER=meta`, usa wa_provider.
- `workers/clientes/system_ia/demos/inmobiliaria/worker.py` (Mica) — default Evolution. Si `WHATSAPP_PROVIDER=meta`, usa wa_provider.

**Importante**: el codigo de los providers legacy (YCloud/Evolution) NO se borro, queda como "mencion" — es la rama default. Para switchear a Meta basta cambiar una env var en el deploy, sin tocar codigo.

### 3. Script CLI `02_OPERACION_COMPARTIDA/scripts/probar_worker.sh`

```bash
export LOVBOT_ADMIN_TOKEN='...'
./probar_worker.sh <phone_number_id> <alias|url>

# Aliases disponibles:
#   arnaldo-demo   → demo inmobiliaria Arnaldo
#   mica-demo      → demo inmobiliaria Mica
#   robert-demo    → bot productivo Robert
#   gastronomia    → demo gastronomia
```

## Workers INTOCADOS (regla de oro)

- ❌ `workers/clientes/arnaldo/maicol/worker.py` — PRODUCCION LIVE, no tocar
- ❌ `workers/clientes/system_ia/lau/worker.py` — PRODUCCION LIVE (dueno real: Arnaldo), no tocar
- ❌ `workers/clientes/lovbot/robert_inmobiliaria/worker.py` — PRODUCCION LIVE Meta nativo

Solo los workers `demos/*` sirven de sandbox para este patron. Cuando un demo pase a cliente real, se adapta el worker del cliente por separado segun el stack que use (Airtable+YCloud para Arnaldo, Airtable+Evolution para Mica, PG+Meta para Robert).

## Flujo paso a paso para usar el numero test

1. **Una vez** (setup inicial): conectar el numero de test via Embedded Signup a la app de Robert → guardar el `phone_number_id` que devuelve Meta.
2. **Cada prueba**:
   - Elegir que worker probar.
   - `./probar_worker.sh <phone_id> <alias>` → cambia el routing.
   - Mandar mensaje al numero desde otro dispositivo.
   - Ver logs del backend: `docker logs agentes-lovbot --tail 50`.
3. **Migrar a cliente real** (cuando aplique):
   - Cliente hace su propio Embedded Signup con su propio numero.
   - Su worker se deploya a su propia agencia (Mica en Easypanel, Arnaldo en Coolify Hostinger, Robert en Coolify Hetzner).
   - Env var del cliente configura el provider final (YCloud, Evolution, o se queda en Meta si es cliente Lovbot).

## Restricciones

- **WABA queda en Robert permanentemente** mientras el numero este en su Tech Provider. Para sacarlo → migracion WABA (1-7 dias en Meta).
- **Mientras Meta App Review este en Revision en curso** (estado 2026-04-20): solo usuarios con rol admin de la app pueden completar el Embedded Signup → perfecto para el numero de test de Arnaldo (admin), NO para clientes externos.
- **Un numero = una WABA a la vez**. No se puede tener el mismo numero en Lovbot y en otra app Meta al mismo tiempo.

## Relacion con otras paginas

- [[wiki/entidades/lovbot-ai]] — Tech Provider que habilita esto
- [[wiki/entidades/arnaldo-ayala]] — beneficiario del patron (socio tecnico de las 3 agencias)
- [[wiki/conceptos/aislamiento-entre-agencias]] — el patron NO rompe aislamiento porque solo usa infra de Robert para el test, el codigo sigue separado por agencia
- [[wiki/conceptos/meta-graph-api]] — protocolo usado por el numero test
- [[wiki/conceptos/matriz-infraestructura]] — WHATSAPP_PROVIDER es una env var que cambia segun agencia destino

## Proximos pasos

- [ ] Numero fisico elegido por Arnaldo (pendiente — ver si usa personal o uno dedicado).
- [ ] Test e2e: conectar nro → switch a demo Arnaldo → mandar mensaje → validar.
- [ ] Repetir con demo Mica para validar que el mismo numero funciona cross-agencia.
- [ ] Adaptar demo gastronomia al mismo patron cuando sea prioridad.
