#!/usr/bin/env bash
#
# test-bot.sh — Script reutilizable para testear bot WhatsApp
# Uso: ./test-bot.sh <cliente> <telefono> <caso_a|caso_b>
#
# Ejemplos:
#   ./test-bot.sh robert 5493765384843 caso_a
#   ./test-bot.sh mica 5493765005465 caso_b
#   ./test-bot.sh maicol 5493764815689 caso_a
#
set -euo pipefail

CLIENTE="${1:-}"
TELEFONO="${2:-}"
CASO="${3:-caso_a}"

if [[ -z "$CLIENTE" || -z "$TELEFONO" ]]; then
  echo "Uso: $0 <cliente> <telefono> <caso_a|caso_b>"
  echo "Clientes soportados: robert, mica, maicol, prueba"
  exit 1
fi

# Resolver base URL según cliente
case "$CLIENTE" in
  robert|lovbot)
    BASE="https://agentes.lovbot.ai/clientes/lovbot/inmobiliaria"
    NOMBRE_LEAD="Arnaldo Test"
    ;;
  mica|system-ia)
    BASE="https://agentes.arnaldoayalaestratega.cloud/mica/demos/inmobiliaria"
    NOMBRE_LEAD="Arnaldo Test"
    ;;
  maicol|arnaldo)
    BASE="https://agentes.arnaldoayalaestratega.cloud/clientes/arnaldo/maicol"
    NOMBRE_LEAD="Arnaldo Test"
    ;;
  prueba)
    BASE="https://agentes.arnaldoayalaestratega.cloud/clientes/arnaldo/prueba"
    NOMBRE_LEAD="Arnaldo Test"
    ;;
  *)
    echo "Cliente no reconocido: $CLIENTE"
    exit 1
    ;;
esac

echo "═══════════════════════════════════════════════════════════"
echo "🤖 Test del bot: $CLIENTE ($BASE)"
echo "   Teléfono: $TELEFONO"
echo "   Caso: $CASO"
echo "═══════════════════════════════════════════════════════════"

# Step 1 — Reset sesión
echo ""
echo "1️⃣ Reset sesión..."
curl -s -X POST "$BASE/admin/reset-sesion/$TELEFONO" | python3 -m json.tool
echo ""

# Step 2 — Simular entrada (Caso A o Caso B)
if [[ "$CASO" == "caso_a" ]]; then
  echo "2️⃣ Simulando lead desde anuncio (Caso A)..."
  curl -s -X POST "$BASE/admin/simular-lead-anuncio/$TELEFONO" \
    -H "Content-Type: application/json" \
    -d "{
      \"headline\":\"Lote en country San Ignacio - USD 18k\",
      \"body\":\"600m2 con escritura inmediata\",
      \"source_url\":\"fb.com/ad/test\",
      \"nombre\":\"$NOMBRE_LEAD\",
      \"mensaje\":\"Hola, vi tu publicación, sigue disponible?\"
    }" | python3 -m json.tool
else
  echo "2️⃣ Simulando mensaje genérico (Caso B)..."
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
            \"contacts\":[{\"profile\":{\"name\":\"$NOMBRE_LEAD\"},\"wa_id\":\"$TELEFONO\"}],
            \"messages\":[{
              \"from\":\"$TELEFONO\",
              \"id\":\"wamid.test$(date +%s)\",
              \"timestamp\":\"$(date +%s)\",
              \"type\":\"text\",
              \"text\":{\"body\":\"Hola, me interesa información sobre propiedades\"}
            }]
          },
          \"field\":\"messages\"
        }]
      }]
    }"
fi
echo ""

# Step 3 — Esperar respuesta del bot
echo "3️⃣ Esperando respuesta del bot..."
TIMEOUT=30
while [[ $TIMEOUT -gt 0 ]]; do
  RESP=$(curl -s "$BASE/admin/ver-sesion/$TELEFONO" 2>/dev/null || echo '{}')
  TIENE_BOT=$(echo "$RESP" | python3 -c "
import json, sys
try:
    d = json.load(sys.stdin)
    bots = [h for h in d.get('historial_ultimos_10', []) if 'Bot:' in h]
    print('1' if bots else '0')
except:
    print('0')
")
  if [[ "$TIENE_BOT" == "1" ]]; then
    break
  fi
  sleep 2
  TIMEOUT=$((TIMEOUT-2))
done

if [[ $TIMEOUT -le 0 ]]; then
  echo "❌ Timeout esperando respuesta del bot"
  exit 1
fi

# Step 4 — Mostrar estado
echo ""
echo "4️⃣ Estado de la sesión:"
echo "───────────────────────────────────────────────────────────"
curl -s "$BASE/admin/ver-sesion/$TELEFONO" | python3 -c "
import json, sys
d = json.load(sys.stdin)
s = d.get('sesion', {})
print(f'  Step: {s.get(\"step\", \"?\")}')
print(f'  Nombre: {s.get(\"nombre\", \"-\")}')
print(f'  Email: {s.get(\"email\", \"-\")}')
print(f'  Objetivo: {s.get(\"resp_objetivo\", \"-\")}')
print(f'  Tipo: {s.get(\"resp_tipo\", \"-\")}')
print(f'  Zona: {s.get(\"resp_zona\", \"-\")}')
print(f'  Presupuesto: {s.get(\"resp_presupuesto\", \"-\")}')
print(f'  Urgencia: {s.get(\"resp_urgencia\", \"-\")}')
print(f'  Score: {s.get(\"score\", \"-\")}')
print(f'  Props: idx {s.get(\"prop_idx\", \"?\")} / total {len(s.get(\"props\", []))}')
print()
print('  Historial:')
for h in d.get('historial_ultimos_10', []):
    print(f'    {h[:180]}')
"
echo ""
echo "✅ Test completado"
echo ""
echo "Podés continuar el test enviando mensajes manualmente:"
echo ""
echo "  curl -X POST $BASE/whatsapp \\"
echo "    -H 'Content-Type: application/json' \\"
echo "    -d '{\"object\":\"whatsapp_business_account\",\"entry\":[{\"changes\":[{\"value\":{\"messaging_product\":\"whatsapp\",\"contacts\":[{\"profile\":{\"name\":\"$NOMBRE_LEAD\"},\"wa_id\":\"$TELEFONO\"}],\"messages\":[{\"from\":\"$TELEFONO\",\"id\":\"wamid.$(date +%s)\",\"type\":\"text\",\"text\":{\"body\":\"MENSAJE_AQUÍ\"}}]},\"field\":\"messages\"}]}]}'"
echo ""
echo "O ver la sesión en cualquier momento:"
echo "  curl $BASE/admin/ver-sesion/$TELEFONO | python3 -m json.tool"
