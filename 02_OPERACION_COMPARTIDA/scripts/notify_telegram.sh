#!/bin/bash
# notify_telegram.sh — Envía mensaje a Telegram de Arnaldo usando el bot del auditor
#
# Uso:
#   ./notify_telegram.sh "TÍTULO" "MENSAJE"
#   ./notify_telegram.sh "🔴 URGENTE" "Bot Maicol no responde"
#   cat archivo.md | ./notify_telegram.sh "📅 Recordatorio"   # lee stdin si hay 1 solo arg
#
# Salida: imprime OK + message_id si éxito, ERROR + descripción si falla.
#         Exit 0 si éxito, 1 si falla.
#
# Lee credencial desde ~/.claude/channels/telegram/.env
# Chat ID leído desde ~/.claude/channels/telegram/access.json (primer allowFrom)

TITULO="${1:-Notificación}"
MENSAJE="${2:-}"

# Si no hay mensaje como arg y hay stdin, leerlo
if [[ -z "$MENSAJE" ]] && [[ ! -t 0 ]]; then
  MENSAJE=$(cat)
fi

if [[ -z "$MENSAJE" ]]; then
  echo "ERROR: falta mensaje. Uso: $0 'título' 'mensaje'" >&2
  exit 1
fi

# Cargar env
ENV_FILE="$HOME/.claude/channels/telegram/.env"
ACCESS_FILE="$HOME/.claude/channels/telegram/access.json"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "ERROR: no encuentro $ENV_FILE" >&2
  exit 1
fi

set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

if [[ -z "$TELEGRAM_BOT_TOKEN" ]]; then
  echo "ERROR: TELEGRAM_BOT_TOKEN vacío en $ENV_FILE" >&2
  exit 1
fi

# Obtener chat_id
CHAT_ID=$(python3 -c "import json; d=json.load(open('$ACCESS_FILE')); print(d.get('allowFrom',['863363759'])[0])" 2>/dev/null || echo "863363759")

# Construir mensaje final — usar HTML parse mode es más robusto (menos caracteres especiales)
# Escapar < > & que son especiales en HTML
TITULO_ESC=$(echo "$TITULO" | sed 's/&/\&amp;/g; s/</\&lt;/g; s/>/\&gt;/g')
MENSAJE_ESC=$(echo "$MENSAJE" | sed 's/&/\&amp;/g; s/</\&lt;/g; s/>/\&gt;/g')

FINAL_MSG="<b>${TITULO_ESC}</b>

${MENSAJE_ESC}"

# Enviar con parse_mode=HTML (más estable que Markdown para chars como _ * ` ~)
RESPONSE=$(curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
  -d "chat_id=${CHAT_ID}" \
  -d parse_mode=HTML \
  --data-urlencode "text=${FINAL_MSG}")

# Parsear resultado — escribir a archivo temp y leer desde Python
TMPFILE=$(mktemp)
echo "$RESPONSE" > "$TMPFILE"

python3 - "$TMPFILE" <<'PYEOF'
import json, sys
path = sys.argv[1]
try:
    with open(path) as f:
        data = json.load(f)
    if data.get("ok"):
        print(f"OK {data['result']['message_id']}")
        sys.exit(0)
    print(f"ERROR: {data.get('description', 'unknown')}")
    sys.exit(1)
except Exception as e:
    print(f"ERROR parseando: {e}")
    sys.exit(1)
PYEOF

EXIT=$?
rm -f "$TMPFILE"
exit $EXIT
