#!/bin/bash
# Hook: detecta el proyecto (Arnaldo / Robert / Mica) desde el path del archivo
# y RECUERDA invocar el subagente correcto antes de editar.
# Si detecta señales de mezcla de stacks (ej: airtable en código Robert), bloquea con warning.

TOOL_INPUT="$1"

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

# ── Detectar proyecto desde el path ───────────────────────────────────────────
PROYECTO=""
SUBAGENTE=""
STACK_PROHIBIDO=""

if [[ "$FILE_PATH" == *"01_PROYECTOS/03_LOVBOT_ROBERT/"* ]] \
   || [[ "$FILE_PATH" == *"workers/clientes/lovbot/"* ]] \
   || [[ "$FILE_PATH" == *"demos/INMOBILIARIA/"* ]]; then
  PROYECTO="ROBERT (Lovbot)"
  SUBAGENTE="proyecto-robert"
  # Stack PROHIBIDO en código Robert
  STACK_PROHIBIDO="airtable_api_key|AIRTABLE_API_KEY|EVOLUTION_API|YCLOUD_API_KEY|appA8QxIhBYYAHw0F"

elif [[ "$FILE_PATH" == *"01_PROYECTOS/02_SYSTEM_IA_MICAELA/"* ]] \
     || [[ "$FILE_PATH" == *"workers/clientes/system_ia/"* ]] \
     || [[ "$FILE_PATH" == *"demos/SYSTEM-IA/"* ]]; then
  PROYECTO="MICA (System IA)"
  SUBAGENTE="proyecto-mica"
  # Stack PROHIBIDO en código Mica
  STACK_PROHIBIDO="LOVBOT_OPENAI_API_KEY|robert_crm|YCLOUD_API_KEY|META_PHONE_NUMBER_ID"

elif [[ "$FILE_PATH" == *"workers/clientes/arnaldo/"* ]] \
     || [[ "$FILE_PATH" == *"demos/back-urbanizaciones/"* ]] \
     || [[ "$FILE_PATH" == *"01_PROYECTOS/01_ARNALDO_AGENCIA/clientes/"* ]]; then
  PROYECTO="ARNALDO (agencia propia)"
  SUBAGENTE="proyecto-arnaldo"
  # Stack PROHIBIDO en código Arnaldo
  STACK_PROHIBIDO="LOVBOT_OPENAI_API_KEY|robert_crm|EVOLUTION_API|appA8QxIhBYYAHw0F"
fi

# Si no detectamos proyecto específico, salir limpio
if [[ -z "$PROYECTO" ]]; then
  exit 0
fi

# ── Si es archivo a editar y existe, escanear contenido por stack prohibido ──
WARNING_MIXED=""
if [[ -n "$STACK_PROHIBIDO" ]] && [[ -f "$FILE_PATH" ]]; then
  MATCHES=$(grep -E "$STACK_PROHIBIDO" "$FILE_PATH" 2>/dev/null | head -3)
  if [[ -n "$MATCHES" ]]; then
    # Escapar comillas para JSON
    MATCHES_ESCAPED=$(echo "$MATCHES" | python3 -c "import sys, json; print(json.dumps(sys.stdin.read()))")
    WARNING_MIXED=" 🚨 MEZCLA DETECTADA: el archivo contiene patrones del stack PROHIBIDO para este proyecto: ${MATCHES_ESCAPED}. NO LO 'CORRIJAS' AGREGANDO MÁS — ES POSIBLEMENTE UN BUG ANTERIOR. AVISÁ AL USUARIO."
  fi
fi

# ── Devolver mensaje a Claude ────────────────────────────────────────────────
MESSAGE="🎯 PROYECTO DETECTADO: ${PROYECTO}. Subagente recomendado: \`${SUBAGENTE}\`. Antes de continuar editando, verificá que NO estás mezclando stacks de otros proyectos.${WARNING_MIXED}"

echo "{\"continue\": true, \"systemMessage\": \"${MESSAGE}\"}"
exit 0
