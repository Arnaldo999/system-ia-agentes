#!/bin/bash
# Hook: Valida sintaxis Python antes de que Claude edite/escriba un .py
# Se ejecuta en PreToolUse para Edit y Write
# Exit code 2 = bloquea la acción

TOOL_INPUT="$1"

# Solo actuar si el archivo es .py
if [[ "$TOOL_INPUT" != *".py"* ]]; then
  exit 0
fi

# Extraer path del archivo del input JSON
FILE_PATH=$(echo "$TOOL_INPUT" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    print(d.get('file_path', d.get('path', '')))
except:
    print('')
" 2>/dev/null)

if [[ -z "$FILE_PATH" ]] || [[ ! -f "$FILE_PATH" ]]; then
  exit 0
fi

# Validar sintaxis Python del archivo actual (antes del cambio)
RESULT=$(python3 -m py_compile "$FILE_PATH" 2>&1)
if [[ $? -ne 0 ]]; then
  echo "⚠️  ADVERTENCIA: $FILE_PATH ya tiene errores de sintaxis antes de editar:" >&2
  echo "$RESULT" >&2
  # No bloqueamos (solo advertimos) — el archivo ya estaba roto
fi

exit 0
