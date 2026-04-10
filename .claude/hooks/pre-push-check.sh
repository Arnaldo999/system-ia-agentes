#!/bin/bash
# Hook: Valida todos los workers Python antes de git push
# Exit code 2 = bloquea el push

TOOL_INPUT="$1"

# Solo actuar en git push
COMMAND=$(echo "$TOOL_INPUT" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    print(d.get('command', ''))
except:
    print('')
" 2>/dev/null)

if [[ "$COMMAND" != *"git push"* ]]; then
  exit 0
fi

WORKERS_DIR="/home/arna/PROYECTOS SYSTEM IA/SYSTEM_IA_MISSION_CONTROL/01_PROYECTOS/01_ARNALDO_AGENCIA/backends/system-ia-agentes/workers"

if [[ ! -d "$WORKERS_DIR" ]]; then
  exit 0
fi

ERRORS=0
ERROR_FILES=""

while IFS= read -r -d '' pyfile; do
  RESULT=$(python3 -m py_compile "$pyfile" 2>&1)
  if [[ $? -ne 0 ]]; then
    ERRORS=$((ERRORS + 1))
    ERROR_FILES="$ERROR_FILES\n  ❌ $pyfile\n     $RESULT"
  fi
done < <(find "$WORKERS_DIR" -name "*.py" -not -path "*/venv/*" -not -path "*/__pycache__/*" -print0)

if [[ $ERRORS -gt 0 ]]; then
  echo "🚫 Push bloqueado — $ERRORS archivo(s) con errores de sintaxis Python:" >&2
  echo -e "$ERROR_FILES" >&2
  echo "" >&2
  echo "Corregí los errores y volvé a intentar el push." >&2
  exit 2
fi

echo "✅ Todos los workers Python validados correctamente ($ERRORS errores)"
exit 0
