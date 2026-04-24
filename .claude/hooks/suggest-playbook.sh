#!/bin/bash
# Hook: UserPromptSubmit
# Detecta si el prompt del usuario menciona un tipo de trabajo que tiene playbook
# y le recuerda a Claude leer el playbook correspondiente ANTES de codear.
#
# Evita repetir errores ya resueltos (caso Maicol 6h → con playbook 30min).
#
# Se configura en .claude/settings.json bajo hooks.UserPromptSubmit.

INPUT=$(cat)

# Extraer el prompt del usuario del JSON de entrada
PROMPT=$(echo "$INPUT" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    # UserPromptSubmit pasa 'prompt' en el JSON
    print(d.get('prompt', '').lower())
except:
    print('')
" 2>/dev/null)

# Si no hay prompt, salir sin hacer nada
if [[ -z "$PROMPT" ]]; then
  exit 0
fi

# Path base de los playbooks (absoluto para que funcione desde cualquier cwd)
PB_BASE="PROYECTO ARNALDO OBSIDIAN/wiki/playbooks"

# ── Matcher: keyword → playbook ──────────────────────────────────────────────
# Orden importa: los más específicos primero (ej: "bot whatsapp" antes que "bot")

PLAYBOOKS_MATCHED=()

# 1. Worker WhatsApp Bot
# Matchea: "bot" + "whatsapp" en cualquier orden/distancia, o frases directas tipo "worker bot", "nuevo bot", "BANT"
if echo "$PROMPT" | grep -qE "(bot.*whatsapp|whatsapp.*bot|worker.*whatsapp|whatsapp.*worker|bant|bot.conversacional|bot.inmobiliari|bot.gastrono|bot.turismo|worker.bot|nuevo.bot|bot.nuevo.*cliente|worker.*inmobiliari|worker.*gastrono)"; then
  PLAYBOOKS_MATCHED+=("${PB_BASE}/worker-whatsapp-bot.md|Bot WhatsApp (BANT + 1-a-1 + LLM parsing)")
fi

# 2. Social Automation (FB+IG)
if echo "$PROMPT" | grep -qE "(redes.sociales|social.automation|facebook.post|instagram.post|publicaci.n.*auto|post.*automatic|bot.comentarios|meta.webhook|fb.*ig|ig.*fb|messenger.*dm|dm.*messenger|publicar.*fb|publicar.*instagram|maicol.social|social.*worker)"; then
  PLAYBOOKS_MATCHED+=("${PB_BASE}/worker-social-automation.md|Social Automation Meta (FB+IG+comentarios+DMs)")
fi

# 3. CRM / Panel HTML
if echo "$PROMPT" | grep -qE "(crm|panel.admin|dashboard|panel.gestion|frontend.*cliente|crm.v[0-9]|persona.unica|contratos.polimorfic|panel.*tenant)"; then
  PLAYBOOKS_MATCHED+=("${PB_BASE}/crm-html-tailwind.md|CRM HTML+Tailwind CDN+JS vanilla")
fi

# 4. Postgres multi-tenant
if echo "$PROMPT" | grep -qE "(postgres.*cliente|cliente.*postgres|bd.*cliente|cliente.*bd|base.de.datos.*cliente|nueva.db|crear.*db|workspace.postgres|lovbot_crm|schema.*postgres|duplicar.*db|clonar.*db)"; then
  PLAYBOOKS_MATCHED+=("${PB_BASE}/postgres-multi-tenant.md|PostgreSQL workspaces (BD aislada por cliente)")
fi

# 5. Airtable schema setup
# Matchea "airtable" como palabra aislada cuando se menciona en contexto de cliente nuevo o schema
if echo "$PROMPT" | grep -qE "(airtable|brandbook.*cliente|base.*brandbook)"; then
  PLAYBOOKS_MATCHED+=("${PB_BASE}/airtable-schema-setup.md|Airtable base + schema estándar")
fi

# 6. Propuesta / landing Coolify
if echo "$PROMPT" | grep -qE "(landing|propuesta|formulario.publico|sitio.*cliente|clientes-publicos|propuesta.comercial|armar.*sitio|armar.*web|sitio.web.*cliente)"; then
  PLAYBOOKS_MATCHED+=("${PB_BASE}/propuesta-cliente-coolify.md|Landing/propuesta en clientes-publicos/")
fi

# Si no hay match, salir limpio
if [[ ${#PLAYBOOKS_MATCHED[@]} -eq 0 ]]; then
  exit 0
fi

# ── Construir mensaje para Claude ────────────────────────────────────────────
MSG="📖 PLAYBOOK(S) RELEVANTE(S) DETECTADO(S) — LEER ANTES DE CODEAR:"$'\n'

for entry in "${PLAYBOOKS_MATCHED[@]}"; do
  path="${entry%%|*}"
  desc="${entry##*|}"
  MSG+=$'\n'"   • \`${path}\` — ${desc}"
done

MSG+=$'\n\n'"Estos playbooks capturan gotchas reales (ej: caso Maicol 6+h de debugging → 30min con playbook). Revisá la tabla de gotchas antes de arrancar. Si descubrís algo nuevo al terminar, agregalo al playbook."

# Output hookSpecificOutput para inyectar el mensaje como context adicional
# (hook UserPromptSubmit usa 'additionalContext' según spec Claude Code)
python3 -c "
import json
msg = '''$MSG'''
print(json.dumps({
    'hookSpecificOutput': {
        'hookEventName': 'UserPromptSubmit',
        'additionalContext': msg
    }
}))
"
exit 0
