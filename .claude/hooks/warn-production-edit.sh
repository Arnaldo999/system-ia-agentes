#!/bin/bash
# Hook: Advierte cuando se edita un worker de producción LIVE
# Workers críticos: maicol (producción real con clientes)

TOOL_INPUT="$1"

# Extraer path del archivo
FILE_PATH=$(echo "$TOOL_INPUT" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    print(d.get('file_path', d.get('path', '')))
except:
    print('')
" 2>/dev/null)

if [[ -z "$FILE_PATH" ]]; then
  exit 0
fi

# Workers de producción live
PROD_PATTERNS=(
  "workers/clientes/arnaldo/maicol"
  "workers/clientes/arnaldo/prueba"
)

for PATTERN in "${PROD_PATTERNS[@]}"; do
  if [[ "$FILE_PATH" == *"$PATTERN"* ]]; then
    # Devolver feedback a Claude para que lo muestre
    echo '{
      "continue": true,
      "systemMessage": "⚠️  PRODUCCIÓN LIVE: Estás editando '"$FILE_PATH"'. Maicol tiene clientes reales activos. Verificá dos veces antes de hacer push."
    }'
    exit 0
  fi
done

exit 0
