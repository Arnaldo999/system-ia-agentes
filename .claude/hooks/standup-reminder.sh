#!/bin/bash
# Hook: SessionStart
# Al abrir sesión nueva de Claude Code, lee .ultimo-cierre.json y:
# - Si nunca se cerró → recordar inicializar con /cierre
# - Si último cierre hace >12h → avisar que corra /apertura
# - Si último cierre <12h → silencio (misma jornada laboral)
#
# Propósito: no perder de vista el backlog cuando hay muchos proyectos.

CIERRE_FILE="/home/arna/PROYECTOS SYSTEM IA/SYSTEM_IA_MISSION_CONTROL/02_OPERACION_COMPARTIDA/standup/.ultimo-cierre.json"

# Si el archivo no existe (setup roto), salir silencioso
if [[ ! -f "$CIERRE_FILE" ]]; then
  exit 0
fi

# Leer y analizar el JSON
ANALYSIS=$(python3 <<EOF
import json
from datetime import datetime, timezone, timedelta

try:
    with open("$CIERRE_FILE") as f:
        data = json.load(f)
except Exception as e:
    print(f"ERROR|{e}")
    exit(0)

ultimo = data.get("ultimo_cierre")
total = data.get("total_items_backlog", 0)
criticos = data.get("criticos", 0)
altos = data.get("altos", 0)

if ultimo is None:
    # Nunca se cerró
    print("NEVER|0|0|0")
    exit(0)

# Parsear timestamp
try:
    # Soporta formato ISO con timezone
    if ultimo.endswith("Z"):
        dt = datetime.fromisoformat(ultimo.replace("Z", "+00:00"))
    else:
        dt = datetime.fromisoformat(ultimo)

    if dt.tzinfo is None:
        # Sin timezone, asumir Argentina UTC-3
        dt = dt.replace(tzinfo=timezone(timedelta(hours=-3)))

    now = datetime.now(timezone.utc)
    horas = (now - dt).total_seconds() / 3600

    print(f"OK|{horas:.0f}|{total}|{criticos}|{altos}")
except Exception as e:
    print(f"ERROR|{e}")
EOF
)

# Parsear resultado
STATUS=$(echo "$ANALYSIS" | cut -d'|' -f1)

# Construir mensaje según estado
MSG=""

case "$STATUS" in
  "NEVER")
    MSG="📋 **Sistema de standup no inicializado**. Nunca ejecutaste \`/cierre\`. El backlog está vacío. Al final de tu próximo día de trabajo, corré \`/cierre\` para capturar tus TODOs abiertos — esto te va a servir cuando tengas muchos proyectos en simultáneo."
    ;;

  "OK")
    HORAS=$(echo "$ANALYSIS" | cut -d'|' -f2)
    TOTAL=$(echo "$ANALYSIS" | cut -d'|' -f3)
    CRITICOS=$(echo "$ANALYSIS" | cut -d'|' -f4)
    ALTOS=$(echo "$ANALYSIS" | cut -d'|' -f5)

    if [[ "$HORAS" -lt 12 ]]; then
      # Mismo día laboral — silencio
      exit 0
    fi

    if [[ "$HORAS" -gt 48 ]]; then
      # Más de 2 días sin cerrar
      MSG="⚠️ **Backlog desactualizado**. Último cierre hace ${HORAS}h. Tenés ${TOTAL} items en backlog"
      if [[ "$CRITICOS" -gt 0 ]]; then
        MSG="${MSG} incluyendo **${CRITICOS} críticos 🔴**"
      fi
      if [[ "$ALTOS" -gt 0 ]]; then
        MSG="${MSG} y ${ALTOS} altos 🟠"
      fi
      MSG="${MSG}. Considerá correr \`/apertura\` para ver urgencias, y \`/cierre\` al final del día para actualizar."
    elif [[ "$HORAS" -gt 12 ]]; then
      # Nueva jornada
      RESUMEN=""
      if [[ "$CRITICOS" -gt 0 ]]; then
        RESUMEN="**${CRITICOS} críticos 🔴**"
      fi
      if [[ "$ALTOS" -gt 0 ]]; then
        if [[ -n "$RESUMEN" ]]; then
          RESUMEN="${RESUMEN} + ${ALTOS} altos 🟠"
        else
          RESUMEN="${ALTOS} altos 🟠"
        fi
      fi
      if [[ -z "$RESUMEN" ]]; then
        RESUMEN="${TOTAL} items abiertos"
      fi
      MSG="🌅 **Nueva jornada** (último cierre hace ${HORAS}h). Backlog: ${RESUMEN}. Corré \`/apertura\` para ver qué atacar primero, o \`/urgencias\` para un resumen compacto."
    fi
    ;;

  "ERROR"|*)
    # No molestar al usuario con errores del hook
    exit 0
    ;;
esac

# Si no hay mensaje, salir silencioso
if [[ -z "$MSG" ]]; then
  exit 0
fi

# Emitir hookSpecificOutput con additionalContext
python3 -c "
import json
msg = '''$MSG'''
print(json.dumps({
    'hookSpecificOutput': {
        'hookEventName': 'SessionStart',
        'additionalContext': msg
    }
}))
"
exit 0
