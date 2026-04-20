#!/usr/bin/env bash
# probar_worker.sh
# ================
# Switch rapido del worker_url asociado a tu numero de test en el Tech
# Provider de Robert (Lovbot). Permite rutear tu numero conectado via
# Embedded Signup a cualquier worker (demo Arnaldo, demo Mica, demo Robert,
# o uno custom) sin desconectar/reconectar el numero de Meta.
#
# Patron "numero de test unico":
#   Tu nro ──► WABA Lovbot (Tech Provider) ──► webhook agentes.lovbot.ai/webhook/meta
#                                                │
#                                                ▼
#                                 Backend route por phone_number_id
#                                                │
#                                                ▼
#                        worker_url → ESTE SCRIPT cambia ese valor
#
# Uso:
#   ./probar_worker.sh <phone_number_id> <alias|url-custom>
#
# Aliases pre-definidos (resueltos al HOST de agentes.lovbot.ai):
#   arnaldo-demo   → /clientes/arnaldo/demo-inmobiliaria/whatsapp
#   mica-demo      → /clientes/system_ia/demos/inmobiliaria/whatsapp
#   robert-demo    → /clientes/lovbot/robert_inmobiliaria/whatsapp
#   gastronomia    → /demos/gastronomia/whatsapp
#
# Ejemplos:
#   ./probar_worker.sh 123456789 mica-demo
#   ./probar_worker.sh 123456789 https://mi-ngrok.ngrok.io/webhook
#
# Requisitos:
#   export LOVBOT_ADMIN_TOKEN='...'   (mismo valor que Coolify Hetzner)

set -euo pipefail

PHONE_ID="${1:-}"
TARGET="${2:-}"
BASE="${LOVBOT_BASE_URL:-https://agentes.lovbot.ai}"
TOKEN="${LOVBOT_ADMIN_TOKEN:-}"

if [[ -z "$PHONE_ID" || -z "$TARGET" ]]; then
  cat <<'USAGE' >&2
Uso: probar_worker.sh <phone_number_id> <alias|url>

Aliases:
  arnaldo-demo   demo inmobiliaria Arnaldo (YCloud por defecto, Meta si WHATSAPP_PROVIDER=meta)
  mica-demo      demo inmobiliaria Mica (Evolution por defecto, Meta si WHATSAPP_PROVIDER=meta)
  robert-demo    bot productivo Robert (Meta nativo)
  gastronomia    demo gastronomia (YCloud)

Env vars:
  LOVBOT_ADMIN_TOKEN   token admin del backend Lovbot (requerido)
  LOVBOT_BASE_URL      default: https://agentes.lovbot.ai
USAGE
  exit 1
fi

if [[ -z "$TOKEN" ]]; then
  echo "❌ LOVBOT_ADMIN_TOKEN no esta exportado" >&2
  exit 2
fi

# Resolver alias → URL
case "$TARGET" in
  arnaldo-demo)
    URL="${BASE}/clientes/arnaldo/demo-inmobiliaria/whatsapp"
    ;;
  mica-demo)
    URL="${BASE}/clientes/system_ia/demos/inmobiliaria/whatsapp"
    ;;
  robert-demo)
    URL="${BASE}/clientes/lovbot/robert_inmobiliaria/whatsapp"
    ;;
  gastronomia)
    URL="${BASE}/demos/gastronomia/whatsapp"
    ;;
  http://*|https://*)
    URL="$TARGET"
    ;;
  *)
    echo "❌ Alias desconocido: $TARGET" >&2
    echo "   Usa uno de: arnaldo-demo, mica-demo, robert-demo, gastronomia, o una URL https://..." >&2
    exit 3
    ;;
esac

echo "→ Tenant phone_id=$PHONE_ID"
echo "→ Nuevo worker_url=$URL"
echo ""

RESP=$(curl -sS -X POST \
  "${BASE}/admin/waba/client/${PHONE_ID}/update-worker-url" \
  -H "Content-Type: application/json" \
  -H "X-Admin-Token: ${TOKEN}" \
  -d "{\"worker_url\": \"${URL}\"}")

echo "$RESP"

if echo "$RESP" | grep -q '"status":"ok"'; then
  echo ""
  echo "✅ Switch OK. Mandale un mensaje al numero de test para ver el worker nuevo respondiendo."
else
  echo ""
  echo "❌ El backend devolvio error — revisa la salida arriba."
  exit 4
fi
