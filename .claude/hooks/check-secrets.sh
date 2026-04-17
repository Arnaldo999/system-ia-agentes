#!/bin/bash
# Hook: detecta posibles secrets en archivos antes de escribirlos/editarlos.
# Bloquea el write si detecta patrones de API keys conocidas, para evitar que Claude
# accidentalmente copie una key del .env local al código fuente.

TOOL_INPUT="$1"

FILE_PATH=$(echo "$TOOL_INPUT" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    print(d.get('file_path', d.get('path', '')))
except:
    print('')
" 2>/dev/null)

CONTENT=$(echo "$TOOL_INPUT" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    # Para Write, el contenido va en 'content'. Para Edit, en 'new_string'.
    print(d.get('content', d.get('new_string', '')))
except:
    print('')
" 2>/dev/null)

if [[ -z "$FILE_PATH" ]] || [[ -z "$CONTENT" ]]; then
  exit 0
fi

# No aplicar a archivos .env (esperados, ya están en .gitignore)
if [[ "$FILE_PATH" == *.env ]] || [[ "$FILE_PATH" == *.env.* ]]; then
  exit 0
fi

# No aplicar a archivos de ejemplo / docs / memoria / wiki (pueden documentar patrones)
if [[ "$FILE_PATH" == *.env.example ]] \
   || [[ "$FILE_PATH" == *".md" ]] \
   || [[ "$FILE_PATH" == *"docs/"* ]] \
   || [[ "$FILE_PATH" == *"memory/"* ]] \
   || [[ "$FILE_PATH" == *"OBSIDIAN/"* ]] \
   || [[ "$FILE_PATH" == *"check-secrets"* ]]; then
  exit 0
fi

# Patrones de secrets reales (no nombres de variables, sino valores)
PATTERNS=(
  'sk-[A-Za-z0-9]{30,}'                      # OpenAI legacy
  'sk-proj-[A-Za-z0-9_-]{30,}'               # OpenAI proj
  'sk-ant-[A-Za-z0-9_-]{30,}'                # Anthropic
  'pat[A-Za-z0-9]{14,}\.[A-Za-z0-9]{60,}'    # Airtable PAT
  'AIza[A-Za-z0-9_-]{35}'                    # Google (Gemini)
  'sk_(live|test)_[A-Za-z0-9]{24,}'          # Stripe
  'AC[a-f0-9]{32}'                           # Twilio SID
  'gh[pousr]_[A-Za-z0-9]{36,}'               # GitHub tokens
  'Bearer [A-Za-z0-9._~+/-]{40,}'            # Bearer token largo
)

DETECTED=""
for pat in "${PATTERNS[@]}"; do
  if echo "$CONTENT" | grep -qE "$pat" 2>/dev/null; then
    DETECTED="Patrón detectado: $pat"
    break
  fi
done

if [[ -n "$DETECTED" ]]; then
  echo "{\"continue\": false, \"systemMessage\": \"🚨 BLOQUEADO: el contenido que intentás escribir a '$FILE_PATH' contiene un posible secret ($DETECTED). Si es intencional y es placeholder, pedí al usuario que verifique. Si es una key real, NUNCA la pongas en código — usá env var.\"}"
  exit 1
fi

exit 0
